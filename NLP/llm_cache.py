"""Small SQLite cache for LLM answers, keyed by provider, model and the exact request.

Re-running a file (or the eval) with unchanged prompts then costs nothing. Any prompt,
schema or model change produces a different key, so stale answers are never reused.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
from pathlib import Path
from typing import Any

_lock = threading.Lock()


def cache_key(*parts: Any) -> str:
    raw = json.dumps(parts, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=30)
    connection.execute("CREATE TABLE IF NOT EXISTS answers (key TEXT PRIMARY KEY, answer TEXT NOT NULL, created TEXT DEFAULT CURRENT_TIMESTAMP)")
    return connection


def get(path: Path, key: str) -> str | None:
    with _lock:
        connection = _connect(path)
        try:
            row = connection.execute("SELECT answer FROM answers WHERE key = ?", (key,)).fetchone()
        finally:
            connection.close()
    return row[0] if row else None


def put(path: Path, key: str, answer: str) -> None:
    with _lock:
        connection = _connect(path)
        try:
            connection.execute("INSERT OR REPLACE INTO answers (key, answer) VALUES (?, ?)", (key, answer))
            connection.commit()
        finally:
            connection.close()
