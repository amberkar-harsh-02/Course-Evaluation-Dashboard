"""Per-run state for LLM calls: token usage counting, an optional per-run API key and an optional model choice.

analysis_pipeline() opens a run with `llm_run(...)`. Every call made inside it (including calls on worker
threads, which receive a copy of the context) adds its token usage to the run's UsageMeter, and uses the
run's own API key and model when they were given. The key lives only in memory for the length of the run.
"""
from __future__ import annotations

import threading
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Iterator

import settings


class LLMAccountError(RuntimeError):
    """The provider refused the account itself (bad key, no credit). Retrying or continuing is pointless."""


class UsageMeter:
    def __init__(self, prices: dict[str, float] | None = None) -> None:
        self._lock = threading.Lock()
        self.llm_calls = 0
        self.cache_hits = 0
        self.input_tokens = 0
        self.cached_input_tokens = 0
        self.output_tokens = 0
        self.billable = False  # True once any paid (hosted) call is made
        # USD per 1M tokens for this run's model; None means the lab's OpenAI prices from settings
        self.prices = prices

    def add_cache_hit(self) -> None:
        with self._lock:
            self.cache_hits += 1

    def add(self, model_choice: str, input_tokens: int, cached_input_tokens: int, output_tokens: int) -> None:
        with self._lock:
            self.llm_calls += 1
            self.input_tokens += int(input_tokens or 0)
            self.cached_input_tokens += int(cached_input_tokens or 0)
            self.output_tokens += int(output_tokens or 0)
            if model_choice != "local":
                self.billable = True

    def _price(self, name: str, setting: str) -> float:
        if self.prices and name in self.prices:
            return float(self.prices[name])
        return float(getattr(settings, setting))

    def cost_usd(self) -> float:
        if not self.billable:
            return 0.0
        uncached = max(0, self.input_tokens - self.cached_input_tokens)
        cost = (
            uncached * self._price("input", "OPENAI_PRICE_INPUT_PER_M")
            + self.cached_input_tokens * self._price("cached_input", "OPENAI_PRICE_CACHED_INPUT_PER_M")
            + self.output_tokens * self._price("output", "OPENAI_PRICE_OUTPUT_PER_M")
        ) / 1_000_000
        return round(cost, 6)

    def as_dict(self) -> dict[str, Any]:
        return {
            "llm_calls": self.llm_calls,
            "cache_hits": self.cache_hits,
            "input_tokens": self.input_tokens,
            "cached_input_tokens": self.cached_input_tokens,
            "output_tokens": self.output_tokens,
            "estimated_cost_usd": self.cost_usd(),
        }


current_meter: ContextVar[UsageMeter | None] = ContextVar("current_meter", default=None)
# The run's API key (a professor's own key) for whichever hosted provider the run uses
key_override: ContextVar[str | None] = ContextVar("key_override", default=None)
# The run's model ID; None means the provider's default (for OpenAI, settings.OPENAI_MODEL)
model_override: ContextVar[str | None] = ContextVar("model_override", default=None)
openai_key_override = key_override  # older name, kept for existing imports


@contextmanager
def llm_run(api_key: str | None = None, model_id: str | None = None,
            prices: dict[str, float] | None = None) -> Iterator[UsageMeter]:
    meter = UsageMeter(prices)
    meter_token = current_meter.set(meter)
    key_token = key_override.set(api_key or None)
    model_token = model_override.set(model_id or None)
    try:
        yield meter
    finally:
        model_override.reset(model_token)
        key_override.reset(key_token)
        current_meter.reset(meter_token)
