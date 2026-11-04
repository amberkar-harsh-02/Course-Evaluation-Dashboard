"""Anthropic and Gemini requests, model choice and per-model cost, with fake HTTP endpoints (no real calls)."""
import pytest

import main
import model_catalog
import settings
from llm_context import LLMAccountError

ANALYSIS_JSON = ('{"topics": [{"topic": "Clarity of explanations", "score": 5, "confidence": 0.9, '
                 '"evidence_quote": "clear", "reasoning": "r", "direction": null}], "general_sentiment_score": null}')


class FakeResponse:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise main.requests.HTTPError(f"HTTP {self.status_code}")


def _is_analysis(text):
    return "analyzing one course-evaluation comment" in text


@pytest.fixture
def fake_hosts(monkeypatch):
    """Answers like the Anthropic Messages API and the Gemini generateContent API, and records each request."""
    calls = []
    behaviour = {"status": 200, "error": None}

    def post(url, headers=None, json=None, timeout=None):
        calls.append({"url": url, "headers": headers, "json": json})
        if behaviour["status"] != 200:
            return FakeResponse(behaviour["status"], {"error": behaviour["error"]})
        if "anthropic.com" in url:
            text = json["messages"][0]["content"]
            content = ANALYSIS_JSON if _is_analysis(text) else "Comments praise clear explanations."
            return FakeResponse(200, {"content": [{"type": "text", "text": content}],
                                      "usage": {"input_tokens": 200, "cache_read_input_tokens": 800, "output_tokens": 100}})
        if "generativelanguage" in url:
            text = json["contents"][0]["parts"][0]["text"]
            content = ANALYSIS_JSON if _is_analysis(text) else "Comments praise clear explanations."
            return FakeResponse(200, {"candidates": [{"content": {"parts": [{"text": "thinking", "thought": True}, {"text": content}]}}],
                                      "usageMetadata": {"promptTokenCount": 1000, "cachedContentTokenCount": 0,
                                                        "candidatesTokenCount": 60, "thoughtsTokenCount": 40}})
        raise AssertionError(f"unexpected URL {url}")

    monkeypatch.setattr(main.requests, "post", post)
    monkeypatch.setattr(main.time, "sleep", lambda *_: None)
    monkeypatch.setattr(settings, "LLM_CACHE", False)
    monkeypatch.setattr(settings, "PIPELINE_MODE", "single")
    return calls, behaviour


def scored_topics(report):
    return [c["topic"] for c in report["categories"] if c.get("scored_comment_count")]


def run(provider, model_id=None, api_key="test-key"):
    return main.analysis_pipeline("TEST", ["Explanations were clear.", "Very clear lectures."], write_files=False,
                                  use_rag=False, model_choice=provider, api_key=api_key, model_id=model_id)


def test_anthropic_uses_the_chosen_model_key_and_structured_output(fake_hosts):
    calls, _ = fake_hosts
    report = run("anthropic", "claude-haiku-5-5", api_key="sk-ant-professor")
    assert report["metadata"]["model_id"] == "claude-haiku-5-5"
    assert scored_topics(report) == ["Clarity of explanations"]
    analysis = next(c for c in calls if "output_config" in c["json"])
    assert analysis["json"]["model"] == "claude-haiku-5-5"
    assert analysis["json"]["output_config"]["format"]["type"] == "json_schema"
    assert all(c["headers"]["x-api-key"] == "sk-ant-professor" for c in calls)


def test_anthropic_cost_uses_the_models_prices(fake_hosts):
    usage = run("anthropic", "claude-sonnet-5-5")["metadata"]["usage"]
    sonnet = model_catalog.find("anthropic", "claude-sonnet-5-5")
    calls = usage["llm_calls"]
    # Each fake call: 200 uncached + 800 cached input tokens, 100 output tokens
    expected = calls * (200 * sonnet["input"] + 800 * sonnet["cached_input"] + 100 * sonnet["output"]) / 1_000_000
    assert usage["input_tokens"] == calls * 1000 and usage["cached_input_tokens"] == calls * 800
    assert usage["estimated_cost_usd"] == pytest.approx(expected, abs=1e-6)


def test_gemini_skips_thought_parts_and_counts_thinking_as_output(fake_hosts):
    calls, _ = fake_hosts
    report = run("gemini", "gemini-2.5-flash", api_key="AIza-professor")
    assert report["metadata"]["model_id"] == "gemini-2.5-flash"
    assert scored_topics(report) == ["Clarity of explanations"]
    assert "gemini-2.5-flash:generateContent" in calls[0]["url"]
    assert calls[0]["headers"]["x-goog-api-key"] == "AIza-professor"
    analysis = next(c for c in calls if "responseJsonSchema" in c["json"]["generationConfig"])
    assert analysis["json"]["generationConfig"]["responseMimeType"] == "application/json"
    usage = report["metadata"]["usage"]
    assert usage["output_tokens"] == usage["llm_calls"] * 100


def test_provider_default_model_is_used_when_none_is_chosen(fake_hosts):
    report = run("gemini")
    assert report["metadata"]["model_id"] == model_catalog.default_model("gemini")["model_id"]


@pytest.mark.parametrize("provider,status,error,message", [
    ("anthropic", 401, {"type": "authentication_error", "message": "invalid x-api-key"}, "Anthropic API key was rejected"),
    ("anthropic", 400, {"type": "invalid_request_error", "message": "Your credit balance is too low"}, "Anthropic account has no credit"),
    ("gemini", 400, {"status": "INVALID_ARGUMENT", "message": "API key not valid. Please pass a valid API key."}, "Google Gemini API key was rejected"),
    ("gemini", 403, {"status": "PERMISSION_DENIED", "message": "denied"}, "Google Gemini API key was rejected"),
])
def test_account_problems_stop_the_run_with_the_provider_name(fake_hosts, provider, status, error, message):
    _, behaviour = fake_hosts
    behaviour.update(status=status, error=error)
    with pytest.raises(LLMAccountError, match=message):
        run(provider)


def test_cache_keys_differ_per_model(monkeypatch):
    seen = []
    monkeypatch.setattr(main.llm_cache, "cache_key", lambda *parts: seen.append(parts[1]) or "k")
    monkeypatch.setattr(main.llm_cache, "get", lambda *_: "cached answer")
    monkeypatch.setattr(settings, "LLM_CACHE", True)
    from llm_context import llm_run
    with llm_run(model_id="claude-opus-5-5"):
        main.call_llm("p", model_choice="anthropic")
    with llm_run():
        main.call_llm("p", model_choice="anthropic")
    assert seen == ["claude-opus-5-5", model_catalog.default_model("anthropic")["model_id"]]


def test_catalog_lists_three_providers_with_one_default_each():
    entries = model_catalog.catalog()
    assert [p["provider"] for p in entries] == ["openai", "anthropic", "gemini"]
    for provider in entries:
        assert sum(m["default"] for m in provider["models"]) == 1
    assert model_catalog.default_model("openai")["model_id"] == settings.OPENAI_MODEL
