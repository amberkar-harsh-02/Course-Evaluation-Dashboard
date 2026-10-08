"""Runtime configuration for the NLP pipeline and API.

Every value can be overridden with an environment variable (or a line in NLP/.env).
The defaults reproduce the setup the lab has been running.
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


def _env(name: str, default: str) -> str:
    value = os.environ.get(name, "").strip()
    return value or default


# LLM endpoints and model IDs
OLLAMA_URL = _env("OLLAMA_URL", "http://10.9.144.10:8001/api/generate")
OLLAMA_MODEL = _env("OLLAMA_MODEL", "qwen35b:latest")
OPENAI_URL = _env("OPENAI_URL", "https://api.openai.com/v1/chat/completions")
OPENAI_MODEL = _env("OPENAI_MODEL", "gpt-5.6-terra")
ANTHROPIC_URL = _env("ANTHROPIC_URL", "https://api.anthropic.com/v1/messages")
ANTHROPIC_MODEL = _env("ANTHROPIC_MODEL", "claude-sonnet-4-6")

# OCR / text-extraction server used by api.py
OCR_URL = _env("OCR_URL", "http://127.0.0.1:8000/api/extract-text")

# "single": one schema-enforced LLM call per comment (topics + scores together).
# "two_step": the older flow, one classification call then one scoring call per topic.
PIPELINE_MODE = _env("PIPELINE_MODE", "single")

# Drop topic scores whose model confidence is under CONFIDENCE_THRESHOLDS in main.py ("on"/"off")
CONFIDENCE_GATE = _env("CONFIDENCE_GATE", "on").lower() != "off"

# How many LLM calls run at the same time. Hosted APIs handle more; the local Mac Studio fewer.
MAX_PARALLEL_API_CALLS = int(_env("MAX_PARALLEL_API_CALLS", "8"))
MAX_PARALLEL_LOCAL_CALLS = int(_env("MAX_PARALLEL_LOCAL_CALLS", "2"))

# Reuse earlier LLM answers for identical prompts (same model, same prompt text). "on"/"off"
LLM_CACHE = _env("LLM_CACHE", "on").lower() != "off"
LLM_CACHE_PATH = Path(_env("LLM_CACHE_PATH", str(BASE_DIR / "cache" / "llm_cache.sqlite")))

# API server
API_HOST = _env("API_HOST", "127.0.0.1")
API_PORT = int(_env("API_PORT", "8001"))
ALLOWED_ORIGINS = [o.strip() for o in _env("ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",") if o.strip()]
# Optional shared secret; when set, every request must send it in the X-API-Key header
API_KEY = _env("NLP_API_KEY", "")

# Bump whenever prompts or scoring rules change, so reports can be compared fairly
PROMPT_VERSION = "2026-10-08.4"

MODEL_IDS = {
    "local": OLLAMA_MODEL,
    "openai": OPENAI_MODEL,
    "anthropic": ANTHROPIC_MODEL,
}


def model_id_for(model_choice: str) -> str:
    return MODEL_IDS.get(model_choice, OLLAMA_MODEL)


def max_parallel_calls(model_choice: str) -> int:
    limit = MAX_PARALLEL_API_CALLS if model_choice in ("openai", "anthropic") else MAX_PARALLEL_LOCAL_CALLS
    return max(1, limit)
