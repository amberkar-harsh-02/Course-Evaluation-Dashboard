"""Database tables for the merged app.

Phase 1 uses `users`. `reports`, `uploads` and `usage_log` are created now so later phases
(credits, merged app, comparisons) need no schema change.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import JSON, BigInteger, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base

# JSONB on Postgres, plain JSON on SQLite (development and tests)
JsonColumn = JSON().with_variant(JSONB(), "postgresql")


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Role:
    ADMIN = "admin"
    PROFESSOR = "professor"
    ALL = (ADMIN, PROFESSOR)


class Status:
    PENDING = "pending"      # registered, waiting for admin approval
    APPROVED = "approved"    # can log in
    REJECTED = "rejected"    # registration declined
    DISABLED = "disabled"    # was approved, access turned off
    ALL = (PENDING, APPROVED, REJECTED, DISABLED)


class CreditMode:
    OUR_KEY_CAPPED = "our_key_capped"
    OUR_KEY_UNLIMITED = "our_key_unlimited"
    OWN_KEY = "own_key"
    ALL = (OUR_KEY_CAPPED, OUR_KEY_UNLIMITED, OWN_KEY)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200))
    department: Mapped[str | None] = mapped_column(String(200), nullable=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), default=Role.PROFESSOR)
    status: Mapped[str] = mapped_column(String(20), default=Status.PENDING, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failed_logins: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Bumped on password change / disable so older login tokens stop working
    token_version: Mapped[int] = mapped_column(Integer, default=0)

    # Phase 2: how this user pays for analyses
    credit_mode: Mapped[str] = mapped_column(String(30), default=CreditMode.OUR_KEY_CAPPED)
    yearly_token_cap: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    encrypted_api_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    api_key_last4: Mapped[str | None] = mapped_column(String(4), nullable=True)

    reports: Mapped[list["Report"]] = relationship(back_populates="owner", foreign_keys="Report.owner_id")


class Upload(Base):
    __tablename__ = "uploads"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    original_filename: Mapped[str] = mapped_column(String(255))
    stored_path: Mapped[str] = mapped_column(String(500))
    size_bytes: Mapped[int] = mapped_column(BigInteger, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    upload_id: Mapped[int | None] = mapped_column(ForeignKey("uploads.id"), nullable=True)
    course: Mapped[str] = mapped_column(String(200))
    term: Mapped[str | None] = mapped_column(String(100), nullable=True)
    model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    overall_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    report_json: Mapped[dict] = mapped_column(JsonColumn)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    owner: Mapped[User] = relationship(back_populates="reports", foreign_keys=[owner_id])


class UsageLog(Base):
    __tablename__ = "usage_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    report_id: Mapped[int | None] = mapped_column(ForeignKey("reports.id"), nullable=True)
    used_own_key: Mapped[bool] = mapped_column(default=False)
    input_tokens: Mapped[int] = mapped_column(BigInteger, default=0)
    cached_input_tokens: Mapped[int] = mapped_column(BigInteger, default=0)
    output_tokens: Mapped[int] = mapped_column(BigInteger, default=0)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
