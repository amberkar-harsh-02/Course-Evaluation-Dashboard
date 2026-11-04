"""Hosted models a professor can choose when they use their own API key.

Only models that support structured (JSON-schema) output are listed, because the pipeline asks for one
schema-checked answer per comment. Prices are USD per 1M tokens and are only used to estimate what a run cost.

Sources, checked 2026-11-04 (update the numbers when a provider changes them):
- OpenAI: developers.openai.com/api/docs/models/gpt-5.6-terra, -luna, -sol
- Anthropic: platform.claude.com/docs/en/about-claude/pricing (cache reads billed at about 10 % of input)
- Google: ai.google.dev/gemini-api/docs/pricing (Gemini 3.8 Flash at its introductory price until 2026-12-31;
  cached input estimated at 25 % of input)
The lab's own model (settings.OPENAI_MODEL and the OPENAI_PRICE_* settings) is always the OpenAI default.
"""
from __future__ import annotations

from typing import Any

import settings

PROVIDERS = {"openai": "OpenAI", "anthropic": "Anthropic", "gemini": "Google Gemini"}

_MODELS: list[dict[str, Any]] = [
    # provider, model_id, label, input, cached input, output, default
    {"provider": "openai", "model_id": "gpt-5.6-luna", "label": "GPT-5.6 Luna (fastest, lowest cost)",
     "input": 0.20, "cached_input": 0.02, "output": 1.20},
    {"provider": "openai", "model_id": "gpt-5.6-sol", "label": "GPT-5.6 Sol (most capable)",
     "input": 4.00, "cached_input": 0.40, "output": 20.00},
    {"provider": "anthropic", "model_id": "claude-sonnet-5-5", "label": "Claude Sonnet 5.5 (recommended)",
     "input": 2.00, "cached_input": 0.20, "output": 10.00, "default": True},
    {"provider": "anthropic", "model_id": "claude-haiku-5-5", "label": "Claude Haiku 5.5 (fastest, lowest cost)",
     "input": 0.10, "cached_input": 0.01, "output": 0.50},
    {"provider": "anthropic", "model_id": "claude-opus-5-5", "label": "Claude Opus 5.5 (most capable)",
     "input": 4.00, "cached_input": 0.40, "output": 20.00},
    {"provider": "gemini", "model_id": "gemini-3.8-flash", "label": "Gemini 3.8 Flash (recommended)",
     "input": 0.75, "cached_input": 0.19, "output": 3.75, "default": True},
    {"provider": "gemini", "model_id": "gemini-2.5-flash", "label": "Gemini 2.5 Flash (lowest cost)",
     "input": 0.30, "cached_input": 0.075, "output": 2.50},
    {"provider": "gemini", "model_id": "gemini-2.5-pro", "label": "Gemini 2.5 Pro (most capable)",
     "input": 1.25, "cached_input": 0.31, "output": 10.00},
]


def _lab_openai_model() -> dict[str, Any]:
    """The lab's OpenAI model, read from settings so .env overrides still apply."""
    return {"provider": "openai", "model_id": settings.OPENAI_MODEL, "label": "GPT-5.6 Terra (recommended)",
            "input": settings.OPENAI_PRICE_INPUT_PER_M, "cached_input": settings.OPENAI_PRICE_CACHED_INPUT_PER_M,
            "output": settings.OPENAI_PRICE_OUTPUT_PER_M, "default": True}


def models() -> list[dict[str, Any]]:
    lab = _lab_openai_model()
    return [lab] + [m for m in _MODELS if not (m["provider"] == "openai" and m["model_id"] == lab["model_id"])]


def find(provider: str | None, model_id: str | None) -> dict[str, Any] | None:
    return next((m for m in models() if m["provider"] == provider and m["model_id"] == model_id), None)


def default_model(provider: str) -> dict[str, Any] | None:
    options = [m for m in models() if m["provider"] == provider]
    return next((m for m in options if m.get("default")), options[0] if options else None)


def catalog() -> list[dict[str, Any]]:
    """What the website shows: providers with their models, without prices."""
    return [
        {"provider": key, "name": name, "models": [
            {"model_id": m["model_id"], "label": m["label"], "default": bool(m.get("default"))}
            for m in models() if m["provider"] == key
        ]}
        for key, name in PROVIDERS.items()
    ]
