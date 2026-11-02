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

# --- Credits (Phase 2) ---
# Yearly AI budget each newly registered professor gets on the lab's OpenAI key, in US dollars
DEFAULT_YEARLY_CAP_USD = float(_env("DEFAULT_YEARLY_CAP_USD", "20"))
# Optional total for all professors on the lab key; runs on the lab key stop once it is used up (0 = no limit)
TOTAL_CREDIT_BUDGET_USD = float(_env("TOTAL_CREDIT_BUDGET_USD", "0"))
# The credit year starts on this month-day (MM-DD), e.g. "01-01" or the date the credits were bought
CREDIT_YEAR_START = _env("CREDIT_YEAR_START", "01-01")
# Fernet key that encrypts professors' own API keys in the database. Generate with:
#   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
# Losing it makes stored keys unreadable (professors would re-enter them).
KEY_ENCRYPTION_SECRET = _env("KEY_ENCRYPTION_SECRET")

# --- Analyses (Phase 3) ---
# The NLP pipeline (NLP/main.py) runs inside this server; the OCR server extracts comments from uploads
NLP_DIR = Path(_env("NLP_DIR", str((BASE_DIR.parent.parent / "NLP").resolve())))
OCR_URL = _env("OCR_URL", "http://127.0.0.1:8000/api/extract-text")
# Uploaded evaluation files are kept here (one folder per user)
STORAGE_DIR = Path(_env("STORAGE_DIR", str(BASE_DIR / "storage")))
MAX_UPLOAD_MB = int(_env("MAX_UPLOAD_MB", "25"))
ALLOWED_UPLOAD_TYPES = (".pdf", ".docx", ".xlsx", ".xls", ".csv")

ALLOWED_ORIGINS =[o.strip() for o in _env("ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",") if o.strip()]
API_HOST = _env("API_HOST", "127.0.0.1")
API_PORT = int(_env("API_PORT", "8010"))
