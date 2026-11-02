"""Merged Course Eval app — Phase 1: accounts, registration and admin approval.

Run:  python app.py   (or: uvicorn app:app --port 8010)
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr, Field, field_validator
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

import config
from database import get_db, init_db
from credits import credit_status, lab_spend_this_year, credit_year_start
from keyvault import KeyVaultError, encrypt_key, is_valid_openai_key
from models import CreditMode, Role, Status, UsageLog, User
from security import (
    as_utc,
    create_access_token,
    get_current_user,
    hash_password,
    require_admin,
    verify_password,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("courseeval")

if not config.JWT_SECRET_KEY:
    raise RuntimeError("JWT_SECRET_KEY is missing. Copy .env.example to .env and set a long random value.")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Course Eval App", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)


# --- Schemas -----------------------------------------------------------------------
def check_password_strength(value: str) -> str:
    if len(value) < config.MIN_PASSWORD_LENGTH:
        raise ValueError(f"Password must be at least {config.MIN_PASSWORD_LENGTH} characters")
    if value.isdigit() or value.isalpha():
        raise ValueError("Password must mix letters with numbers or symbols")
    return value


class RegisterRequest(BaseModel):
    email: EmailStr
    name: str = Field(min_length=2, max_length=200)
    department: str | None = Field(default=None, max_length=200)
    password: str = Field(max_length=200)

    _strong = field_validator("password")(check_password_strength)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(max_length=200)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(max_length=200)
    new_password: str = Field(max_length=200)

    _strong = field_validator("new_password")(check_password_strength)


class UserOut(BaseModel):
    id: int
    email: str
    name: str
    department: str | None
    role: str
    status: str
    created_at: datetime
    reviewed_at: datetime | None
    last_login_at: datetime | None
    credit_mode: str
    yearly_cap_usd: float | None
    has_own_key: bool
    api_key_last4: str | None

    @classmethod
    def of(cls, user: User) -> "UserOut":
        return cls(
            id=user.id, email=user.email, name=user.name, department=user.department, role=user.role,
            status=user.status, created_at=user.created_at, reviewed_at=user.reviewed_at,
            last_login_at=user.last_login_at, credit_mode=user.credit_mode, yearly_cap_usd=user.yearly_cap_usd,
            has_own_key=bool(user.encrypted_api_key), api_key_last4=user.api_key_last4,
        )


class RoleUpdate(BaseModel):
    role: str

    @field_validator("role")
    @classmethod
    def valid_role(cls, value: str) -> str:
        if value not in Role.ALL:
            raise ValueError(f"role must be one of {Role.ALL}")
        return value


class ApiKeyRequest(BaseModel):
    api_key: str = Field(max_length=300)


class CreditUpdate(BaseModel):
    credit_mode: str
    yearly_cap_usd: float | None = Field(default=None, ge=0, le=100000)

    @field_validator("credit_mode")
    @classmethod
    def valid_mode(cls, value: str) -> str:
        if value not in CreditMode.ALL:
            raise ValueError(f"credit_mode must be one of {CreditMode.ALL}")
        return value


def normalize_email(email: str) -> str:
    return email.strip().lower()


# --- Auth --------------------------------------------------------------------------
@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.post("/api/auth/register", status_code=status.HTTP_201_CREATED)
def register(req: RegisterRequest, db: Session = Depends(get_db)):
    email = normalize_email(req.email)
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="An account with this email already exists")
    user = User(
        email=email, name=req.name.strip(), department=(req.department or "").strip() or None,
        password_hash=hash_password(req.password), role=Role.PROFESSOR, status=Status.PENDING,
    )
    db.add(user)
    db.commit()
    logger.info("New registration waiting for approval: user %s", user.id)
    return {"message": "Registration received. You can sign in after an administrator approves your account."}


@app.post("/api/auth/login")
def login(req: LoginRequest, db: Session = Depends(get_db)):
    email = normalize_email(req.email)
    user = db.scalar(select(User).where(User.email == email))
    now = datetime.now(timezone.utc)

    locked_until = as_utc(user.locked_until) if user else None
    if locked_until and locked_until > now:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                            detail="Too many failed attempts. Try again in a few minutes.")

    if user is None or not verify_password(req.password, user.password_hash if user else None):
        if user is not None:
            user.failed_logins += 1
            if user.failed_logins >= config.MAX_FAILED_LOGINS:
                user.locked_until = now + timedelta(minutes=config.LOCKOUT_MINUTES)
                user.failed_logins = 0
            db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password")

    user.failed_logins = 0
    user.locked_until = None
    if user.status == Status.PENDING:
        db.commit()
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Your account is waiting for administrator approval")
    if user.status in (Status.REJECTED, Status.DISABLED):
        db.commit()
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Your account does not have access")

    user.last_login_at = now
    db.commit()
    return {"access_token": create_access_token(user), "token_type": "bearer", "user": UserOut.of(user)}


@app.get("/api/auth/me")
def me(user: User = Depends(get_current_user)):
    return UserOut.of(user)


@app.post("/api/auth/change-password")
def change_password(req: ChangePasswordRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not verify_password(req.current_password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Current password is incorrect")
    user.password_hash = hash_password(req.new_password)
    user.token_version += 1  # sign out other sessions
    db.commit()
    return {"message": "Password changed. Please sign in again.", "access_token": create_access_token(user)}


# --- My credits and own API key --------------------------------------------------------
@app.get("/api/me/credits")
def my_credits(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return credit_status(db, user)


@app.put("/api/me/api-key")
def save_api_key(req: ApiKeyRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    key = req.api_key.strip()
    if not is_valid_openai_key(key):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="That does not look like an OpenAI API key (it should start with sk-)")
    try:
        user.encrypted_api_key = encrypt_key(key)
    except KeyVaultError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))
    user.api_key_last4 = key[-4:]
    db.commit()
    logger.info("User %s saved an own API key", user.id)
    return credit_status(db, user)


@app.delete("/api/me/api-key")
def delete_api_key(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    user.encrypted_api_key = None
    user.api_key_last4 = None
    db.commit()
    return credit_status(db, user)


# --- Admin -------------------------------------------------------------------------
def _target(db: Session, user_id: int) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


def _set_status(db: Session, admin: User, user_id: int, new_status: str, allowed_from: tuple[str, ...]) -> User:
    user = _target(db, user_id)
    if user.id == admin.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="You cannot change your own account status")
    if user.status not in allowed_from:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Cannot change a {user.status} account to {new_status}")
    user.status = new_status
    user.reviewed_at = datetime.now(timezone.utc)
    user.reviewed_by = admin.id
    if new_status != Status.APPROVED:
        user.token_version += 1  # end any open sessions
    db.commit()
    logger.info("Admin %s set user %s to %s", admin.id, user.id, new_status)
    return user


@app.get("/api/admin/users")
def list_users(
    status_filter: str | None = Query(default=None, alias="status"),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    query = select(User).order_by(User.created_at.desc())
    if status_filter:
        if status_filter not in Status.ALL:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"status must be one of {Status.ALL}")
        query = query.where(User.status == status_filter)
    return [UserOut.of(u) for u in db.scalars(query)]


@app.get("/api/admin/summary")
def admin_summary(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    counts = dict(db.execute(select(User.status, func.count()).group_by(User.status)).all())
    return {s: counts.get(s, 0) for s in Status.ALL}


@app.post("/api/admin/users/{user_id}/approve")
def approve(user_id: int, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    return UserOut.of(_set_status(db, admin, user_id, Status.APPROVED, (Status.PENDING, Status.REJECTED)))


@app.post("/api/admin/users/{user_id}/reject")
def reject(user_id: int, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    return UserOut.of(_set_status(db, admin, user_id, Status.REJECTED, (Status.PENDING,)))


@app.post("/api/admin/users/{user_id}/disable")
def disable(user_id: int, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    return UserOut.of(_set_status(db, admin, user_id, Status.DISABLED, (Status.APPROVED,)))


@app.post("/api/admin/users/{user_id}/enable")
def enable(user_id: int, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    return UserOut.of(_set_status(db, admin, user_id, Status.APPROVED, (Status.DISABLED,)))


@app.patch("/api/admin/users/{user_id}/role")
def set_role(user_id: int, req: RoleUpdate, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    user = _target(db, user_id)
    if user.id == admin.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="You cannot change your own role")
    user.role = req.role
    user.token_version += 1
    db.commit()
    return UserOut.of(user)


@app.patch("/api/admin/users/{user_id}/credits")
def set_credits(user_id: int, req: CreditUpdate, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    user = _target(db, user_id)
    user.credit_mode = req.credit_mode
    if req.credit_mode == CreditMode.OUR_KEY_CAPPED:
        user.yearly_cap_usd = req.yearly_cap_usd if req.yearly_cap_usd is not None else config.DEFAULT_YEARLY_CAP_USD
    db.commit()
    logger.info("Admin %s set credits for user %s: %s %s", admin.id, user.id, user.credit_mode, user.yearly_cap_usd)
    return {"user": UserOut.of(user), "credits": credit_status(db, user)}


@app.get("/api/admin/usage")
def usage_overview(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    """Lab-credit spend this credit year: total, budget and per professor."""
    start = credit_year_start()
    rows = db.execute(
        select(
            UsageLog.user_id,
            func.count(UsageLog.id),
            func.coalesce(func.sum(case((UsageLog.used_own_key.is_(False), UsageLog.cost_usd), else_=0.0)), 0.0),
            func.coalesce(func.sum(UsageLog.input_tokens), 0),
            func.coalesce(func.sum(UsageLog.output_tokens), 0),
        ).where(UsageLog.created_at >= start).group_by(UsageLog.user_id)
    ).all()
    users = {u.id: u for u in db.scalars(select(User).where(User.id.in_([r[0] for r in rows])))} if rows else {}
    per_user = [{
        "user_id": user_id,
        "email": users[user_id].email if user_id in users else None,
        "credit_mode": users[user_id].credit_mode if user_id in users else None,
        "yearly_cap_usd": users[user_id].yearly_cap_usd if user_id in users else None,
        "runs": runs,
        "lab_cost_usd": round(float(cost), 4),
        "input_tokens": int(tokens_in),
        "output_tokens": int(tokens_out),
    } for user_id, runs, cost, tokens_in, tokens_out in rows]
    total = lab_spend_this_year(db)
    budget = config.TOTAL_CREDIT_BUDGET_USD or None
    return {
        "credit_year_start": start.date().isoformat(),
        "lab_spend_usd": total,
        "budget_usd": budget,
        "budget_remaining_usd": round(budget - total, 4) if budget else None,
        "per_user": sorted(per_user, key=lambda row: row["lab_cost_usd"], reverse=True),
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=config.API_HOST, port=config.API_PORT)
