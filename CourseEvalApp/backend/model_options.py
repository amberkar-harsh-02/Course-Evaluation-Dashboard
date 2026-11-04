"""The AI providers and models a professor can choose for their own key.

The list lives in NLP/model_catalog.py, next to the code that calls the providers, so the website and the
pipeline can never disagree about which models exist.
"""
from __future__ import annotations

import importlib
import sys
from typing import Any

import config

_module = None


def _catalog_module():
    global _module
    if _module is None:
        nlp_dir = str(config.NLP_DIR)
        if nlp_dir not in sys.path:
            sys.path.insert(0, nlp_dir)
        _module = importlib.import_module("model_catalog")
    return _module


def catalog() -> list[dict[str, Any]]:
    return _catalog_module().catalog()


def providers() -> dict[str, str]:
    return dict(_catalog_module().PROVIDERS)


def find(provider: str | None, model_id: str | None) -> dict[str, Any] | None:
    return _catalog_module().find(provider, model_id)


def default_model(provider: str) -> dict[str, Any] | None:
    return _catalog_module().default_model(provider)


def resolve(provider: str | None, model_id: str | None) -> tuple[str, dict[str, Any]]:
    """The provider and model a saved own key runs with. Older keys (no provider saved) are OpenAI keys."""
    provider = provider or "openai"
    model = find(provider, model_id) or default_model(provider) or default_model("openai")
    return model["provider"], model
