"""Side-by-side comparison of a professor's reports (Phase 4).

Only summary numbers leave the server: overall score, per-topic averages, Pace direction, general
sentiment and rating-table means. Reports are ordered by term (e.g. "Spring 2025" before "Fall 2025"),
falling back to the date the report was created.
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any

OTHER_TOPICS = {"None of the above / Other", "Uncategorized/Unrated"}
LOW_SAMPLE = 5            # fewer scored comments than this: treat the topic average as directional only
NOTABLE_CHANGE = 0.3      # topic changes at least this big (on the 1-5 scale) are listed as highlights
# Reports made before this prompt version used the old Pace scale (1 = too fast, 2 = too slow, ...)
PACE_SCALE_FIXED_IN = "2026-10-08.3"

_SEASONS = {"winter": 1, "spring": 2, "summer": 3, "fall": 4, "autumn": 4}


def term_sort_key(term: str | None, created_at: datetime | None) -> tuple:
    """'Fall 2025', '25-Fall', 'F25', 'Spring 2026' -> (year, season). Unknown terms sort last, by creation date."""
    text = (term or "").lower()
    season = next((rank for name, rank in _SEASONS.items() if name in text), None)
    year = None
    full = re.search(r"(20\d{2})", text)
    if full:
        year = int(full.group(1))
    else:
        short = re.search(r"(?<!\d)(\d{2})(?!\d)", text)
        if short:
            year = 2000 + int(short.group(1))
    if season is None:
        letter = re.search(r"(?<![a-z])([wsuf])\s*-?\s*\d{2}", text)  # e.g. "F25", "s 26"
        if letter:
            season = {"w": 1, "s": 2, "u": 3, "f": 4}[letter.group(1)]
    moment = created_at or datetime.min
    if year is None:
        return (1, 0, 0, moment)
    return (0, year, season or 0, moment)


def _number(value: Any) -> float | None:
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def _normalize_question(text: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", re.sub(r"\s+", " ", (text or "").lower())).strip()


def summarize_report(report_id: int, course: str, term: str | None, created_at: datetime, data: dict) -> dict:
    """Pull the numbers needed for comparison out of one stored report."""
    topics: dict[str, dict] = {}
    pace_directions = None
    for category in data.get("categories") or []:
        topic = category.get("topic")
        if not topic or topic in OTHER_TOPICS:
            continue
        scored = int(category.get("scored_comment_count") or 0)
        topics[topic] = {
            "average_score": _number(category.get("average_score")),
            "scored_comments": scored,
            "low_sample": scored < LOW_SAMPLE,
        }
        if topic == "Pace" and isinstance(category.get("direction_counts"), dict):
            pace_directions = category["direction_counts"]

    metadata = data.get("metadata") or {}
    ratings = {}
    for table in data.get("quantitative") or []:
        mean = _number(table.get("mean"))
        if table.get("question") and mean is not None:
            ratings[_normalize_question(table["question"])] = {"question": table["question"], "mean": mean, "n": table.get("n")}

    return {
        "id": report_id,
        "course": course,
        "term": term,
        "created_at": created_at,
        "overall_score": _number(data.get("overall_score")),
        "general_sentiment": _number((data.get("general_sentiment") or {}).get("average_score")),
        "comments": metadata.get("processed_comments"),
        "prompt_version": metadata.get("prompt_version"),
        "model_id": metadata.get("model_id") or data.get("model"),
        "topics": topics,
        "pace_directions": pace_directions,
        "ratings": ratings,
    }


def _change(first: float | None, last: float | None) -> float | None:
    return round(last - first, 2) if first is not None and last is not None else None


def build_comparison(summaries: list[dict]) -> dict:
    ordered = sorted(summaries, key=lambda s: term_sort_key(s["term"], s["created_at"]))

    topic_names = []
    for summary in ordered:
        for topic in summary["topics"]:
            if topic not in topic_names:
                topic_names.append(topic)

    rows = []
    for topic in topic_names:
        cells = [summary["topics"].get(topic) for summary in ordered]
        scores = [cell["average_score"] if cell else None for cell in cells]
        known = [(i, s) for i, s in enumerate(scores) if s is not None]
        change = _change(known[0][1], known[-1][1]) if len(known) >= 2 else None
        reliable = len(known) >= 2 and not cells[known[0][0]]["low_sample"] and not cells[known[-1][0]]["low_sample"]
        rows.append({"topic": topic, "cells": cells, "change": change, "change_is_reliable": reliable})

    highlights = sorted(
        (row for row in rows if row["change"] is not None and row["change_is_reliable"] and abs(row["change"]) >= NOTABLE_CHANGE),
        key=lambda row: row["change"],
    )
    improved = [{"topic": r["topic"], "change": r["change"]} for r in reversed(highlights) if r["change"] > 0][:3]
    declined = [{"topic": r["topic"], "change": r["change"]} for r in highlights if r["change"] < 0][:3]

    # Rating-table questions that appear in at least two of the reports
    rating_keys = []
    for summary in ordered:
        for key in summary["ratings"]:
            if key not in rating_keys:
                rating_keys.append(key)
    rating_rows = []
    for key in rating_keys:
        cells = [summary["ratings"].get(key) for summary in ordered]
        present = [c for c in cells if c]
        if len(present) >= 2:
            rating_rows.append({
                "question": present[0]["question"],
                "means": [c["mean"] if c else None for c in cells],
                "change": _change(present[0]["mean"], present[-1]["mean"]),
            })

    warnings = []
    if len({s["course"].strip().lower() for s in ordered}) > 1:
        warnings.append("These reports are for different courses, so differences may reflect the course rather than the teaching.")
    versions = [s["prompt_version"] for s in ordered]
    if any(v is None or v < PACE_SCALE_FIXED_IN for v in versions) and "Pace" in topic_names:
        warnings.append("Some reports were made before the Pace scale was corrected, so their Pace scores are not comparable.")
    if len({v for v in versions if v}) > 1:
        warnings.append("These reports were analyzed with different versions of the scoring instructions; small differences may come from that.")
    if any(row["change"] is not None and not row["change_is_reliable"] for row in rows):
        warnings.append(f"Topics with fewer than {LOW_SAMPLE} scored comments in a report are marked; treat their changes as rough indications.")

    return {
        "reports": [{k: s[k] for k in ("id", "course", "term", "created_at", "overall_score", "general_sentiment",
                                       "comments", "pace_directions")} for s in ordered],
        "overall_change": _change(ordered[0]["overall_score"], ordered[-1]["overall_score"]) if len(ordered) >= 2 else None,
        "topics": rows,
        "improved": improved,
        "declined": declined,
        "ratings": rating_rows,
        "warnings": warnings,
    }
