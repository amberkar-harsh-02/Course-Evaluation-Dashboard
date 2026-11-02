"""Settings for the merged Course Eval app. Every value comes from the environment (or backend/.env)."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


def _env(name: str, default: str = "") -> str:
    value = os.environ.get(name, "").strip()
    return value or default


# Postgres in production, e.g. postgresql+psycopg2://user:password@localhost:5432/courseeval
# Falls back to a local SQLite file for development.
DATABASE_URL = _env("DATABASE_URL", f"sqlite:///{(BASE_DIR / 'courseeval_dev.db').as_posix()}")

# Signs login tokens. Required: the app refuses to start without it.
JWT_SECRET_KEY = _env("JWT_SECRET_KEY")
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_MINUTES = int(_env("ACCESS_TOKEN_MINUTES", "120"))

MIN_PASSWORD_LENGTH = 10

# Brute-force protection: after this many wrong passwords for one email, wait LOCKOUT_MINUTES
MAX_FAILED_LOGINS = int(_env("MAX_FAILED_LOGINS", "5"))
LOCKOUT_MINUTES = int(_env("LOCKOUT_MINUTES", "15"))

ALLOWED_ORIGINS = [o.strip() for o in _env("ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",") if o.strip()]
API_HOST = _env("API_HOST", "127.0.0.1")
API_PORT = int(_env("API_PORT", "8010"))
