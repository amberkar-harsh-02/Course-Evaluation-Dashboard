import json
import re
import sys
from pathlib import Path

import pytest

NLP_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(NLP_DIR))

import main  # noqa: E402
import settings  # noqa: E402


class FakeLLM:
    """Deterministic stand-in for call_llm so tests never hit a real model.

    Rules, keyed on words in the comment:
      "fast"  -> topic Pace, score 2, direction too_fast
      "clear" -> topic Clarity of explanations, score 5
      "lowconf" -> scored with confidence 0.1 (gets dropped by the gate)
      "offtopic" -> two-step scorer says topic_supported=false; single mode returns no usable topic
      "boom-classify" / "boom-score" -> raise, to simulate model errors
      "best professor" -> generic, general sentiment 5
      anything else -> generic with no tone
    Works for both the single-call prompt and the older two-step prompts.
    """

    def __init__(self):
        self.calls = []
        self.schemas = []

    def __call__(self, prompt, model_choice="local", temperature=0.1, timeout=90, max_retries=0, schema=None, json_mode=True):
        self.calls.append(prompt)
        self.schemas.append(schema)
        feedback = re.search(r'FEEDBACK:\s*"""(.*?)"""', prompt, re.S)
        text = feedback.group(1).lower() if feedback else ""

        if "analyzing one course-evaluation comment" in prompt:
            if "boom-classify" in text or "boom-score" in text:
                raise RuntimeError("analysis exploded")
            topics = []
            confidence = 0.1 if "lowconf" in text else 0.9
            if "fast" in text:
                topics.append({"topic": "Pace", "score": 2, "confidence": confidence, "evidence_quote": "fast",
                               "reasoning": "r", "direction": "too_fast"})
            if "clear" in text or "lowconf" in text:
                topics.append({"topic": "Clarity of explanations", "score": 5, "confidence": confidence,
                               "evidence_quote": "clear", "reasoning": "r", "direction": None})
            if "offtopic" in text:
                topics.append({"topic": "Not a real topic", "score": 3, "confidence": 0.9, "evidence_quote": "",
                               "reasoning": "", "direction": None})
            general = 5 if not topics and "best professor" in text else None
            return json.dumps({"topics": topics, "general_sentiment_score": general})

        if "classifying one course-evaluation comment" in prompt:
            if "boom-classify" in text:
                raise RuntimeError("classification exploded")
            topics = []
            if "fast" in text:
                topics.append("Pace")
            if "clear" in text or "lowconf" in text or "offtopic" in text or "boom-score" in text:
                topics.append("Clarity of explanations")
            return json.dumps({"topics": topics or [main.OTHER], "evidence": {}})
        if "scoring one course-evaluation comment" in prompt:
            if "boom-score" in text:
                raise RuntimeError("scoring exploded")
            if "offtopic" in text:
                return json.dumps({"topic_supported": False, "sentiment": None, "score": None, "confidence": 0.9})
            confidence = 0.1 if "lowconf" in text else 0.9
            score = 2 if "TOPIC: Pace" in prompt else 5
            return json.dumps({"topic_supported": True, "sentiment": "x", "score": score, "confidence": confidence,
                               "evidence_quote": "q", "reasoning": "r"})
        return "Comments mention the topic."


@pytest.fixture(params=["single", "two_step"])
def pipeline_mode(request, monkeypatch):
    monkeypatch.setattr(settings, "PIPELINE_MODE", request.param)
    return request.param


@pytest.fixture
def fake_llm(monkeypatch, pipeline_mode):
    fake = FakeLLM()
    monkeypatch.setattr(main, "call_llm", fake)
    monkeypatch.setattr(settings, "CONFIDENCE_GATE", True)
    # Keep the regex topic hints out of the way so tests only see the fake model's topics
    monkeypatch.setattr(main, "add_high_precision_topic_hints", lambda comment, topics: list(topics))
    return fake
