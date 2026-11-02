"""Admin command line for the merged app.

    python manage.py create-admin     # first admin account (prompts; nothing is hard-coded)
    python manage.py list-users
"""
from __future__ import annotations

import getpass
import sys
from datetime import datetime, timezone

from sqlalchemy import select

import config
from database import SessionLocal, init_db
from models import Role, Status, User
from security import hash_password


def create_admin() -> None:
    init_db()
    email = input("Admin email: ").strip().lower()
    name = input("Full name: ").strip()
    password = getpass.getpass(f"Password (at least {config.MIN_PASSWORD_LENGTH} characters): ")
    if len(password) < config.MIN_PASSWORD_LENGTH or password != getpass.getpass("Repeat password: "):
        sys.exit("Passwords did not match or are too short; nothing was created.")

    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == email))
        if user is None:
            user = User(email=email, name=name or email)
            db.add(user)
        user.password_hash = hash_password(password)
        user.role = Role.ADMIN
        user.status = Status.APPROVED
        user.reviewed_at = datetime.now(timezone.utc)
        user.token_version = (user.token_version or 0) + 1
        db.commit()
        print(f"Admin account ready: {email}")


def list_users() -> None:
    init_db()
    with SessionLocal() as db:
        for user in db.scalars(select(User).order_by(User.created_at)):
            print(f"{user.id:>4}  {user.status:<9} {user.role:<9} {user.email}  ({user.name})")


if __name__ == "__main__":
    commands = {"create-admin": create_admin, "list-users": list_users}
    if len(sys.argv) != 2 or sys.argv[1] not in commands:
        sys.exit(__doc__)
    commands[sys.argv[1]]()
