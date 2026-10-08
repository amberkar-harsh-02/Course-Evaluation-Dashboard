"""Measure analysis_pipeline against the human-labeled baselines.

Usage (from NLP/):
    python eval.py --model openai
    python eval.py --model local --no-rag --limit 20

Needs HUMAN_CATEGORIZED_OUTPUT.csv and HUMAN_SENTIMENT_BASELINE.csv in this folder (kept locally,
not in git). Results go to eval_runs/<timestamp>_<model>/ (also git-ignored, because they contain
student comments).
"""
from __future__ import annotations

import argparse
import csv
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import settings
from main import (
    OTHER,
    TOPICS,
    analysis_pipeline,
    canonical_comment_key,
    load_classification_examples,
    load_sentiment_examples,
    sentiment_from_score,
)

BASE_DIR = Path(__file__).resolve().parent


def safe_divide(numerator: float, denominator: float) -> float:
    return numerator / denominator if denominator else 0.0


def f1(precision: float, recall: float) -> float:
    return safe_divide(2 * precision * recall, precision + recall)


def predicted_assignments(report: dict[str, Any]) -> tuple[dict[str, set[str]], dict[tuple[str, str], Any]]:
    """Map each comment to its predicted topics, and each (comment, topic) to its predicted score."""
    topics_by_comment: dict[str, set[str]] = {}
    score_by_pair: dict[tuple[str, str], Any] = {}
    for category in report["categories"]:
        for comment in category["comments"]:
            key = canonical_comment_key(comment["feedback"])
            topics_by_comment.setdefault(key, set()).add(category["topic"])
            score_by_pair[(key, category["topic"])] = comment.get("score")
    return topics_by_comment, score_by_pair


def topic_metrics(gold: list[dict[str, Any]], predicted: dict[str, set[str]]) -> dict[str, Any]:
    per_topic = {topic: {"tp": 0, "fp": 0, "fn": 0} for topic in TOPICS}
    exact_matches = 0
    for example in gold:
        key = canonical_comment_key(example["feedback"])
        gold_topics = set(example["topics"])
        pred_topics = predicted.get(key, set())
        exact_matches += gold_topics == pred_topics
        for topic in TOPICS:
            if topic in pred_topics and topic in gold_topics:
                per_topic[topic]["tp"] += 1
            elif topic in pred_topics:
                per_topic[topic]["fp"] += 1
            elif topic in gold_topics:
                per_topic[topic]["fn"] += 1

    tp = sum(v["tp"] for v in per_topic.values())
    fp = sum(v["fp"] for v in per_topic.values())
    fn = sum(v["fn"] for v in per_topic.values())
    micro_p, micro_r = safe_divide(tp, tp + fp), safe_divide(tp, tp + fn)
    per_topic_f1 = {}
    for topic, v in per_topic.items():
        if v["tp"] + v["fp"] + v["fn"] == 0:
            continue
        p, r = safe_divide(v["tp"], v["tp"] + v["fp"]), safe_divide(v["tp"], v["tp"] + v["fn"])
        per_topic_f1[topic] = round(f1(p, r), 3)

    return {
        "comments": len(gold),
        "micro_precision": round(micro_p, 3),
        "micro_recall": round(micro_r, 3),
        "micro_f1": round(f1(micro_p, micro_r), 3),
        "macro_f1": round(safe_divide(sum(per_topic_f1.values()), len(per_topic_f1)), 3),
        "exact_match": round(safe_divide(exact_matches, len(gold)), 3),
        "per_topic_f1": per_topic_f1,
    }


def score_metrics(gold: list[dict[str, Any]], predicted: dict[tuple[str, str], Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    rows = []
    errors = []
    sentiment_agree = 0
    for example in gold:
        key = canonical_comment_key(example["feedback"])
        pred = predicted.get((key, example["topic"]))
        pred_score = pred if isinstance(pred, int) else None
        rows.append({
            "feedback": example["feedback"],
            "topic": example["topic"],
            "human_score": example["score"],
            "model_score": pred_score if pred_score is not None else "",
            "topic_found": (key, example["topic"]) in predicted,
        })
        if pred_score is None:
            continue
        errors.append(abs(pred_score - example["score"]))
        sentiment_agree += sentiment_from_score(pred_score) == example["sentiment"]

    scored = len(errors)
    return {
        "pairs": len(gold),
        "coverage": round(safe_divide(scored, len(gold)), 3),
        "mae": round(safe_divide(sum(errors), scored), 3),
        "exact": round(safe_divide(sum(e == 0 for e in errors), scored), 3),
        "within_1": round(safe_divide(sum(e <= 1 for e in errors), scored), 3),
        "sentiment_agreement": round(safe_divide(sentiment_agree, scored), 3),
    }, rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--model", default="local", choices=["local", "openai", "anthropic"])
    parser.add_argument("--no-rag", action="store_true", help="run without retrieved human examples in prompts")
    parser.add_argument("--limit", type=int, default=0, help="only evaluate the first N unique comments")
    parser.add_argument("--out", type=Path, default=BASE_DIR / "eval_runs")
    args = parser.parse_args()

    topic_gold = load_classification_examples()
    score_gold = load_sentiment_examples()
    if not topic_gold and not score_gold:
        raise SystemExit("No baseline CSVs found next to eval.py; nothing to evaluate.")

    comments: list[str] = []
    seen = set()
    for example in topic_gold + score_gold:
        key = canonical_comment_key(example["feedback"])
        if key not in seen:
            seen.add(key)
            comments.append(example["feedback"])
    if args.limit:
        comments = comments[: args.limit]
        keep = {canonical_comment_key(c) for c in comments}
        topic_gold = [e for e in topic_gold if canonical_comment_key(e["feedback"]) in keep]
        score_gold = [e for e in score_gold if canonical_comment_key(e["feedback"]) in keep]

    print(f"Evaluating {len(comments)} comments with model={args.model} rag={not args.no_rag} ...")
    started = time.time()
    report = analysis_pipeline("EVAL", comments, write_files=False, use_rag=not args.no_rag, model_choice=args.model)
    runtime = round(time.time() - started, 1)

    predicted_topics, predicted_scores = predicted_assignments(report)
    topics = topic_metrics(topic_gold, predicted_topics)
    scores, score_rows = score_metrics(score_gold, predicted_scores)
    other_share = safe_divide(
        sum(1 for c in report["categories"] if c["topic"] == OTHER for _ in c["comments"]), len(comments)
    )

    summary = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "model_choice": args.model,
        "model_id": settings.model_id_for(args.model),
        "prompt_version": settings.PROMPT_VERSION,
        "rag": not args.no_rag,
        "comments": len(comments),
        "runtime_seconds": runtime,
        "other_share": round(other_share, 3),
        "topics": topics,
        "scores": scores,
        "pipeline_metadata": report["metadata"],
    }

    run_dir = args.out / f"{datetime.now():%Y%m%d_%H%M%S}_{args.model}"
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (run_dir / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    with open(run_dir / "scores.csv", "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(score_rows[0].keys()) if score_rows else ["feedback"])
        writer.writeheader()
        writer.writerows(score_rows)

    print(json.dumps({k: summary[k] for k in ("model_id", "prompt_version", "runtime_seconds", "other_share")}, indent=2))
    print("topics:", json.dumps({k: v for k, v in topics.items() if k != "per_topic_f1"}))
    print("scores:", json.dumps(scores))
    print(f"Saved to {run_dir}")


if __name__ == "__main__":
    main()
