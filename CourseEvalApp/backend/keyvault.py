"""Encryption for professors' own OpenAI keys.

Keys are encrypted with Fernet (AES-128-CBC + HMAC) using KEY_ENCRYPTION_SECRET from the environment.
The database only ever holds the encrypted value and the last 4 characters. The plain key is decrypted
in memory just before an analysis run and is never logged or returned by the API.
"""
from __future__ import annotations

import re

from cryptography.fernet import Fernet, InvalidToken

import config

OPENAI_KEY_PATTERN = re.compile(r"^sk-[A-Za-z0-9_\-]{20,200}$")


class KeyVaultError(RuntimeError):
    pass


def _fernet() -> Fernet:
    if not config.KEY_ENCRYPTION_SECRET:
        raise KeyVaultError("Storing own API keys is not set up on this server (KEY_ENCRYPTION_SECRET is missing).")
    try:
        return Fernet(config.KEY_ENCRYPTION_SECRET.encode())
    except (ValueError, TypeError) as exc:
        raise KeyVaultError("KEY_ENCRYPTION_SECRET is not a valid Fernet key.") from exc


def is_valid_openai_key(key: str) -> bool:
    return bool(OPENAI_KEY_PATTERN.fullmatch(key or ""))


def encrypt_key(key: str) -> str:
    return _fernet().encrypt(key.encode()).decode()


def decrypt_key(token: str) -> str:
    try:
        return _fernet().decrypt(token.encode()).decode()
    except InvalidToken as exc:
        raise KeyVaultError("The stored API key can't be decrypted. Please enter it again.") from exc
