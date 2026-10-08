import main
import settings


def run(comments):
    return main.analysis_pipeline("TEST", comments, write_files=False, use_rag=False, model_choice="openai")


def category(report, topic):
    return next(c for c in report["categories"] if c["topic"] == topic)


def test_dedupe_comments_removes_exact_duplicates():
    unique, removed = main.dedupe_comments(["Great  class", "Great class", "", "Other"])
    assert unique == ["Great class", "Other"]
    assert removed == 1


def test_parse_helpers():
    assert main.parse_optional_score("score: 4") == 4
    assert main.parse_optional_score("null") is None
    assert main.parse_optional_score(9) == 5
    assert main.parse_confidence("85%") == 0.85
    assert main.parse_confidence(70) == 0.7
    assert main.parse_confidence("n/a") == 0.0


def test_scores_and_overall_score(fake_llm):
    report = run(["Lectures were way too fast.", "Explanations were clear.", "Too fast but very clear."])
    assert category(report, "Pace")["average_score"] == 2
    assert category(report, "Clarity of explanations")["average_score"] == 5
    # Per-comment means: 2, 5, (2+5)/2 = 3.5 -> overall mean 3.5
    assert report["overall_score"] == 3.5
    assert report["metadata"]["scored_comments"] == 3


def test_generic_comment_goes_to_other(fake_llm):
    report = run(["Best professor ever!"])
    other = category(report, main.OTHER)
    assert [c["feedback"] for c in other["comments"]] == ["Best professor ever!"]
    assert other["comments"][0]["scoring_status"] == "not_applicable"
    assert report["overall_score"] is None


def test_drop_reasons_are_counted(fake_llm, pipeline_mode):
    report = run(["lowconf clear", "offtopic clear"])
    drops = report["metadata"]["dropped_topic_assignments"]
    assert drops["low_confidence"] == 1
    if pipeline_mode == "two_step":
        # The separate scorer can reject a topic the classifier picked
        assert drops["topic_unsupported"] == 1
        assert drops["all_topics_rejected"] == 2
        assert len(category(report, main.OTHER)["comments"]) == 2
    else:
        # Single call: unknown topic names are ignored, the valid Clarity score survives
        assert drops["all_topics_rejected"] == 1
        assert [c["feedback"] for c in category(report, "Clarity of explanations")["comments"]] == ["offtopic clear"]


def test_confidence_gate_can_be_switched_off(fake_llm, monkeypatch):
    monkeypatch.setattr(main.settings, "CONFIDENCE_GATE", False)
    report = run(["lowconf clear"])
    assert report["metadata"]["dropped_topic_assignments"]["low_confidence"] == 0
    assert category(report, "Clarity of explanations")["average_score"] == 5


def test_model_errors_are_reported_not_lost(fake_llm, monkeypatch, pipeline_mode):
    monkeypatch.setattr(main, "MODEL_TASK_MAX_RETRIES", 1)
    report = run(["boom-classify", "boom-score clear"])
    meta = report["metadata"]
    statuses = {c["feedback"]: c["scoring_status"] for c in category(report, main.OTHER)["comments"]}
    assert statuses["boom-classify"] == "classification_error"
    assert "boom-score clear" in statuses
    if pipeline_mode == "two_step":
        assert meta["classification_errors"] == 1
        assert meta["scoring_errors"] == 1
    else:
        assert meta["classification_errors"] == 2


def test_single_mode_extras(fake_llm, pipeline_mode):
    if pipeline_mode != "single":
        return
    report = run(["Lectures were way too fast.", "Best professor ever!"])
    assert fake_llm.schemas[0] is main.ANALYSIS_SCHEMA
    pace = category(report, "Pace")
    assert pace["direction_counts"]["too_fast"] == 1
    assert pace["comments"][0]["direction"] == "too_fast"
    assert report["general_sentiment"] == {"average_score": 5, "scored_comments": 1, "positive": 1, "neutral": 0, "negative": 0}
    # Generic tone never leaks into the topic-based overall score
    assert report["overall_score"] == 2


def test_report_shape_is_backward_compatible(fake_llm):
    report = run(["Explanations were clear."])
    assert set(report) >= {"course_id", "model", "overall_score", "category_scores", "topic_summaries", "categories", "metadata"}
    assert len(report["category_scores"]) == 12
    assert len(report["topic_summaries"]) == 13
    comment = category(report, "Clarity of explanations")["comments"][0]
    # Original fields must all stay; new fields may be added
    assert set(comment) >= {"feedback", "classification_status", "topic_supported", "evidence_quote", "sentiment",
                            "score", "confidence", "scoring_status", "reasoning"}
    assert report["quantitative"] == []


def test_question_context_reaches_prompts_and_report(fake_llm):
    report = main.analysis_pipeline(
        "TEST",
        [{"text": "Explanations were clear.", "question": "What helped you learn?"}],
        write_files=False, use_rag=False, model_choice="openai",
        quantitative=[{"question": "Overall rating", "n": 10, "mean": 4.2, "distribution": {"5": 5}}],
        extraction={"parser": "tabular-export", "warnings": ["w"]},
    )
    assert any("What helped you learn?" in prompt for prompt in fake_llm.calls)
    comment = category(report, "Clarity of explanations")["comments"][0]
    assert comment["question"] == "What helped you learn?"
    assert report["quantitative"][0]["mean"] == 4.2
    assert report["metadata"]["parser"] == "tabular-export"
    assert report["metadata"]["extraction_warnings"] == ["w"]


def test_non_teaching_answers_are_skipped_without_llm_calls(fake_llm):
    report = main.analysis_pipeline(
        "TEST",
        [{"text": "I took AP chem in high school", "question": "Did you feel prepared?", "non_teaching_question": True}],
        write_files=False, use_rag=False, model_choice="openai",
    )
    assert report["metadata"]["non_teaching_skipped"] == 1
    other = category(report, main.OTHER)["comments"][0]
    assert other["classification_status"] == "skipped_question"
    assert not any("classifying one course-evaluation comment" in prompt for prompt in fake_llm.calls)


def test_plain_strings_still_work_and_dedupe(fake_llm):
    report = run(["Explanations were clear.", "Explanations were  clear.", {"text": "Explanations were clear."}])
    assert report["metadata"]["processed_comments"] == 1
    assert report["metadata"]["duplicates_removed"] == 2
    assert report["metadata"]["model_id"] == settings.OPENAI_MODEL
    assert report["metadata"]["prompt_version"] == settings.PROMPT_VERSION


def test_progress_callback_and_order_with_parallel_calls(fake_llm, monkeypatch):
    monkeypatch.setattr(main.settings, "MAX_PARALLEL_API_CALLS", 4)
    events = []
    comments = [f"Explanations were clear number {i}." for i in range(10)]
    report = main.analysis_pipeline("TEST", comments, write_files=False, use_rag=False, model_choice="openai",
                                    progress=lambda stage, done, total: events.append((stage, done, total)))
    # Comment order is kept even though calls finish in any order
    assert [c["feedback"] for c in category(report, "Clarity of explanations")["comments"]] == comments
    assert ("comments", 10, 10) in events and events[-1][0] == "summaries"


def test_llm_cache_reuses_answers(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(main.settings, "LLM_CACHE", True)
    monkeypatch.setattr(main.settings, "LLM_CACHE_PATH", tmp_path / "cache.sqlite")
    monkeypatch.setattr(main, "_request_llm", lambda *args: calls.append(args) or '{"ok": 1}')
    assert main.call_llm("same prompt", model_choice="openai") == '{"ok": 1}'
    assert main.call_llm("same prompt", model_choice="openai") == '{"ok": 1}'
    assert main.call_llm("other prompt", model_choice="openai") == '{"ok": 1}'
    assert len(calls) == 2


def test_bullets_never_reach_the_report(fake_llm):
    report = run(["� Explanations were clear.", "Strengths:\n• clear examples\n• fast grading"])
    texts = [c["feedback"] for cat in report["categories"] for c in cat["comments"]]
    assert "Explanations were clear." in texts
    assert "Strengths: clear examples; fast grading" in texts
    assert not any(ch in t for t in texts for ch in "•�")
