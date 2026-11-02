"""Token counting, per-run API keys and account errors, with a fake OpenAI HTTP endpoint (no real calls)."""
import json

import pytest

import main
import settings
from llm_context import LLMAccountError, UsageMeter, llm_run


class FakeResponse:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise main.requests.HTTPError(f"HTTP {self.status_code}")


@pytest.fixture
def fake_openai(monkeypatch):
    """Answers like the OpenAI chat API; records the Authorization header of each call."""
    calls = []
    behaviour = {"status": 200, "error_code": None}

    def post(url, headers=None, json=None, timeout=None):
        calls.append(headers.get("Authorization"))
        if behaviour["status"] != 200:
            return FakeResponse(behaviour["status"], {"error": {"code": behaviour["error_code"]}})
        prompt = json["messages"][0]["content"]
        if "analyzing one course-evaluation comment" in prompt:
            content = '{"topics": [{"topic": "Clarity of explanations", "score": 5, "confidence": 0.9, "evidence_quote": "clear", "reasoning": "r", "direction": null}], "general_sentiment_score": null}'
        else:
            content = "Comments praise clear explanations."
        return FakeResponse(200, {
            "choices": [{"message": {"content": content}}],
            "usage": {"prompt_tokens": 1000, "prompt_tokens_details": {"cached_tokens": 800}, "completion_tokens": 100},
        })

    monkeypatch.setattr(main.requests, "post", post)
    monkeypatch.setattr(settings, "LLM_CACHE", False)
    monkeypatch.setattr(settings, "PIPELINE_MODE", "single")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-lab-shared-key")
    return calls, behaviour


def run(**kwargs):
    return main.analysis_pipeline("TEST", ["Explanations were clear.", "Very clear lectures."], write_files=False,
                                  use_rag=False, model_choice="openai", **kwargs)


def test_usage_and_cost_are_reported(fake_openai, monkeypatch):
    monkeypatch.setattr(settings, "OPENAI_PRICE_INPUT_PER_M", 2.0)
    monkeypatch.setattr(settings, "OPENAI_PRICE_CACHED_INPUT_PER_M", 0.2)
    monkeypatch.setattr(settings, "OPENAI_PRICE_OUTPUT_PER_M", 12.0)
    usage = run()["metadata"]["usage"]
    calls = usage["llm_calls"]
    assert calls == len(fake_openai[0]) and calls >= 2
    assert usage["input_tokens"] == 1000 * calls
    assert usage["cached_input_tokens"] == 800 * calls
    assert usage["output_tokens"] == 100 * calls
    # per call: 200 uncached * $2 + 800 cached * $0.20 + 100 output * $12, per million tokens
    assert usage["estimated_cost_usd"] == pytest.approx(calls * (200 * 2 + 800 * 0.2 + 100 * 12) / 1_000_000)


def test_shared_key_is_used_by_default(fake_openai):
    run()
    assert set(fake_openai[0]) == {"Bearer sk-lab-shared-key"}


def test_own_key_is_used_for_every_call_including_worker_threads(fake_openai, monkeypatch):
    monkeypatch.setattr(settings, "MAX_PARALLEL_API_CALLS", 4)
    run(api_key="sk-professor-own-key")
    assert fake_openai[0] and set(fake_openai[0]) == {"Bearer sk-professor-own-key"}


def test_own_key_does_not_leak_into_the_next_run(fake_openai):
    run(api_key="sk-professor-own-key")
    fake_openai[0].clear()
    run()
    assert set(fake_openai[0]) == {"Bearer sk-lab-shared-key"}


def test_rejected_key_stops_the_run(fake_openai):
    fake_openai[1]["status"] = 401
    with pytest.raises(LLMAccountError, match="rejected"):
        run(api_key="sk-wrong")


def test_no_credit_stops_the_run(fake_openai):
    fake_openai[1].update(status=429, error_code="insufficient_quota")
    with pytest.raises(LLMAccountError, match="no credit"):
        run()


def test_cache_hits_are_free(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "LLM_CACHE", True)
    monkeypatch.setattr(settings, "LLM_CACHE_PATH", tmp_path / "cache.sqlite")
    monkeypatch.setattr(main, "_request_llm", lambda *args: '{"ok": 1}')
    with llm_run() as meter:
        main.call_llm("same prompt", model_choice="openai")
        main.call_llm("same prompt", model_choice="openai")
    assert meter.cache_hits == 1


def test_local_model_usage_costs_nothing():
    meter = UsageMeter()
    meter.add("local", 5000, 0, 500)
    assert meter.cost_usd() == 0.0
    assert meter.as_dict()["input_tokens"] == 5000
