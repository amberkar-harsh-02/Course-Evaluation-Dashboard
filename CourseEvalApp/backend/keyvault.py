"""Encryption for professors' own API keys (OpenAI, Anthropic or Google Gemini).

Keys are encrypted with Fernet (AES-128-CBC + HMAC) using KEY_ENCRYPTION_SECRET from the environment.
The database only ever holds the encrypted value and the last 4 characters. The plain key is decrypted
in memory just before an analysis run and is never logged or returned by the API.
"""
from __future__ import annotations

import re

from cryptography.fernet import Fernet, InvalidToken

import config

OPENAI_KEY_PATTERN = re.compile(r"^sk-[A-Za-z0-9_\-]{20,200}$")
# Key formats from each provider's docs: Anthropic keys start with sk-ant-, Google API keys with AIza
KEY_PATTERNS = {
    "openai": OPENAI_KEY_PATTERN,
    "anthropic": re.compile(r"^sk-ant-[A-Za-z0-9_\-]{20,200}$"),
    "gemini": re.compile(r"^AIza[A-Za-z0-9_\-]{30,60}$"),
}
KEY_HINTS = {
    "openai": "an OpenAI API key (it should start with sk-)",
    "anthropic": "an Anthropic API key (it should start with sk-ant-)",
    "gemini": "a Google Gemini API key (it should start with AIza)",
}


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
    return is_valid_key("openai", key)


def is_valid_key(provider: str, key: str) -> bool:
    pattern = KEY_PATTERNS.get(provider)
    if pattern is None or not pattern.fullmatch(key or ""):
        return False
    # An Anthropic key also matches the looser OpenAI pattern; keep each key with its own provider
    return not (provider == "openai" and key.startswith("sk-ant-"))


def encrypt_key(key: str) -> str:
    return _fernet().encrypt(key.encode()).decode()


def decrypt_key(token: str) -> str:
    try:
        return _fernet().decrypt(token.encode()).decode()
    except InvalidToken as exc:
        raise KeyVaultError("The stored API key can't be decrypted. Please enter it again.") from exc
