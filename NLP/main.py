from __future__ import annotations
import csv
import json
import logging
import re
import time
import os
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any
import requests
from data import SCORING_RUBRIC, TOPIC_DEFS, TOPIC_KEYS
import settings
import llm_cache
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parents[0]
OTHER = "None of the above / Other"
TOPICS = list(TOPIC_KEYS) + [OTHER]

CLASSIFICATION_BASELINE_PATH = BASE_DIR / "HUMAN_CATEGORIZED_OUTPUT.csv"
SENTIMENT_BASELINE_PATH = BASE_DIR / "HUMAN_SENTIMENT_BASELINE.csv"
RAG_CLASSIFICATION_EXAMPLE_COUNT = 2
RAG_SENTIMENT_EXAMPLE_COUNT = 1
RAG_MIN_SIMILARITY = 0.06
LLM_MAX_RETRIES = 2
MODEL_TASK_MAX_RETRIES = 3
MIN_RELIABLE_CATEGORY_COMMENTS = 5
LOW_CONFIDENCE_THRESHOLD = 0.35

CONFIDENCE_THRESHOLDS = {
    "Assessment": 0.45,
    "Workload": 0.45,
    "Pace": 0.40,
    "Clarity of explanations": 0.35,
    "Classroom atmosphere": 0.35,
    "Course organization and structure": 0.40,
    "default": 0.35,
}

RETRIEVAL_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "but", "by", "class", "course", 
    "did", "do", "for", "from", "had", "has", "have", "he", "her", "his", "i", 
    "in", "instructor", "is", "it", "me", "my", "of", "on", "or", "professor", 
    "she", "students", "that", "the", "this", "to", "very", "was", "were", "with",
}

def normalize_comment(comment: str) -> str:
    return re.sub(r"\s+", " ", comment).strip()

def canonical_comment_key(comment: str) -> str:
    text = unicodedata.normalize("NFKD", comment).encode("ascii", "ignore").decode("ascii")
    text = text.casefold()
    return " ".join(re.findall(r"[a-z0-9]+", text))

def dedupe_comments(raw_comments: list[str]) -> tuple[list[str], int]:
    seen_keys = set()
    unique_comments = []
    duplicate_count = 0
    for comment in raw_comments:
        normalized = normalize_comment(comment)
        if not normalized:
            continue
        if normalized in seen_keys:
            duplicate_count += 1
            continue
        seen_keys.add(normalized)
        unique_comments.append(normalized)
    return unique_comments, duplicate_count

def retrieval_tokens(text: str) -> set[str]:
    return set(token for token in canonical_comment_key(text).split() if len(token) > 2 and token not in RETRIEVAL_STOPWORDS)

def retrieval_similarity(left: str, right: str) -> float:
    left_key = canonical_comment_key(left)
    right_key = canonical_comment_key(right)
    if not left_key or not right_key:
        return 0.0
    if left_key == right_key:
        return 1.0

    left_tokens = retrieval_tokens(left)
    right_tokens = retrieval_tokens(right)
    if left_tokens and right_tokens:
        overlap = left_tokens & right_tokens
        containment = len(overlap) / min(len(left_tokens), len(right_tokens))
        jaccard = len(overlap) / len(left_tokens | right_tokens)
    else:
        containment = 0.0
        jaccard = 0.0

    fuzzy_ratio = SequenceMatcher(None, left_key, right_key).ratio()
    return (0.55 * containment) + (0.25 * jaccard) + (0.20 * fuzzy_ratio)

def is_truthy_label(value: Any) -> bool:
    text = str(value or "").strip().casefold()
    return bool(text) and text not in {"0", "false", "n", "nan", "no", "none"}

def truncate_example_text(text: str, max_chars: int = 420) -> str:
    text = normalize_comment(text)
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3].rstrip() + "..."

def load_classification_examples(path: Path = CLASSIFICATION_BASELINE_PATH) -> list[dict[str, Any]]:
    if not path.exists():
        return []

    examples = []
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            feedback = normalize_comment(row.get("Feedback", ""))
            if not feedback:
                continue

            topics = [topic for topic in TOPICS if is_truthy_label(row.get(topic))]
            if not topics:
                topics = [OTHER]
            if OTHER in topics and len(topics) > 1:
                topics = [topic for topic in topics if topic != OTHER] or [OTHER]

            examples.append({"feedback": feedback, "topics": topics})

    return examples

def load_sentiment_examples(path: Path = SENTIMENT_BASELINE_PATH) -> list[dict[str, Any]]:
    if not path.exists():
        return []

    examples = []
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            feedback = normalize_comment(row.get("Feedback", ""))
            topic = str(row.get("Topic", "")).strip()
            sentiment = str(row.get("Sentiment", "neutral")).strip().lower()
            reasoning = normalize_comment(row.get("Reasoning", ""))
            if not feedback or topic not in TOPIC_KEYS:
                continue
            if sentiment not in {"positive", "negative", "neutral"}:
                sentiment = "neutral"
            try:
                score = max(1, min(5, int(row.get("Score", 3))))
            except (TypeError, ValueError):
                score = 3

            examples.append({
                "feedback": feedback,
                "topic": topic,
                "sentiment": sentiment,
                "score": score,
                "reasoning": reasoning,
            })

    return examples

def example_matches_topic(example: dict[str, Any], topic: str | None) -> bool:
    if topic is None:
        return True

    topics = example.get("topics")
    if isinstance(topics, str):
        topics = [item.strip() for item in re.split(r"[;|]", topics) if item.strip()]
    if isinstance(topics, (list, tuple, set)) and topic in topics:
        return True

    example_topic = example.get("topic")
    if isinstance(example_topic, str):
        return example_topic.strip() == topic
    if isinstance(example_topic, (list, tuple, set)):
        return topic in example_topic

    return False

def retrieve_similar_examples(comment: str, examples: list[dict[str, Any]], limit: int, topic: str | None = None, exclude_exact_match: bool = True) -> list[dict[str, Any]]:
    if not examples or limit <= 0:
        return []

    comment_key = canonical_comment_key(comment)
    scored_examples = []
    for example in examples:
        if not example_matches_topic(example, topic):
            continue

        example_feedback = str(example.get("feedback", ""))
        example_key = canonical_comment_key(example_feedback)
        if exclude_exact_match and comment_key == example_key:
            continue

        similarity = retrieval_similarity(comment, example_feedback)
        if similarity < RAG_MIN_SIMILARITY:
            continue

        scored_examples.append((similarity, example))

    scored_examples.sort(key=lambda item: item[0], reverse=True)
    retrieved = []
    for similarity, example in scored_examples[:limit]:
        retrieved_example = dict(example)
        retrieved_example["similarity"] = round(similarity, 3)
        retrieved.append(retrieved_example)
    return retrieved

def format_classification_examples(examples: list[dict[str, Any]]) -> str:
    if not examples:
        return "[]"

    compact_examples = [{
        "similarity": example.get("similarity", 0.0),
        "feedback": truncate_example_text(str(example.get("feedback", ""))),
        "human_topics": example.get("topics", []),
    } for example in examples]
    return json.dumps(compact_examples, indent=2)

def format_sentiment_examples(examples: list[dict[str, Any]]) -> str:
    if not examples:
        return "[]"

    compact_examples = [{
        "similarity": example.get("similarity", 0.0),
        "feedback": truncate_example_text(str(example.get("feedback", ""))),
        "human_sentiment": example.get("sentiment", "neutral"),
        "human_score": example.get("score", 3),
        "human_reasoning": truncate_example_text(str(example.get("reasoning", "")), 180),
    } for example in examples]
    return json.dumps(compact_examples, indent=2)

def extract_json_object(text: str) -> dict[str, Any]:
    json_start = text.find("{")
    json_end = text.rfind("}") + 1
    if json_start == -1 or json_end <= json_start:
        raise ValueError("No JSON object found")
    return json.loads(text[json_start:json_end])


def call_llm(prompt: str, model_choice: str = "local", temperature: float = 0.1, timeout: int = 90, max_retries: int = LLM_MAX_RETRIES, schema: dict[str, Any] | None = None, json_mode: bool = True) -> str:
    """Send one prompt to the chosen model and return its text.

    With `schema`, the provider is asked to enforce that JSON schema (OpenAI structured outputs,
    Anthropic forced tool call, Ollama `format`). Returned text is then always the JSON object.
    `json_mode=False` asks for plain prose (used for topic summaries).
    Answers are cached in SQLite (settings.LLM_CACHE), keyed by provider, model and the full request.
    """
    key = None
    if settings.LLM_CACHE:
        key = llm_cache.cache_key(model_choice, settings.model_id_for(model_choice), prompt, schema, json_mode, temperature)
        cached = llm_cache.get(settings.LLM_CACHE_PATH, key)
        if cached is not None:
            return cached
    answer = _request_llm(prompt, model_choice, temperature, timeout, max_retries, schema, json_mode)
    if key is not None and answer:
        llm_cache.put(settings.LLM_CACHE_PATH, key, answer)
    return answer


def _request_llm(prompt: str, model_choice: str, temperature: float, timeout: int, max_retries: int, schema: dict[str, Any] | None, json_mode: bool) -> str:
    last_error: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            if model_choice == "openai":
                api_key = os.environ.get("OPENAI_API_KEY", "").strip()
                body: dict[str, Any] = {
                    "model": settings.OPENAI_MODEL,
                    "messages": [{"role": "user", "content": prompt}],
                    "reasoning_effort": "low",
                }
                if schema is not None:
                    body["response_format"] = {"type": "json_schema", "json_schema": {"name": "comment_analysis", "strict": True, "schema": schema}}
                response = requests.post(
                    settings.OPENAI_URL,
                    headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                    json=body,
                    timeout=max(timeout, 180),
                )
                response.raise_for_status()
                return response.json()["choices"][0]["message"]["content"]

            elif model_choice == "anthropic":
                api_key = os.environ.get("ANTHROPIC_API_KEY", "")
                body = {
                    "model": settings.ANTHROPIC_MODEL,
                    "max_tokens": 2048,
                    "temperature": temperature,
                }
                if schema is not None:
                    body["messages"] = [{"role": "user", "content": prompt}]
                    body["tools"] = [{"name": "record_analysis", "description": "Record the analysis of the comment.", "input_schema": schema}]
                    body["tool_choice"] = {"type": "tool", "name": "record_analysis"}
                else:
                    suffix = "\n\nRespond strictly with JSON format." if json_mode else ""
                    body["messages"] = [{"role": "user", "content": prompt + suffix}]
                response = requests.post(
                    settings.ANTHROPIC_URL,
                    headers={
                        "x-api-key": api_key,
                        "anthropic-version": "2023-06-01",
                        "content-type": "application/json"
                    },
                    json=body,
                    timeout=timeout,
                )
                response.raise_for_status()
                content = response.json()["content"]
                tool_use = next((block for block in content if block.get("type") == "tool_use"), None)
                if tool_use is not None:
                    return json.dumps(tool_use["input"])
                return next((block["text"] for block in content if block.get("type") == "text"), "")

            else:
                # Local Ollama (lab Mac Studio). Sampling settings go under "options".
                body = {
                    "model": settings.OLLAMA_MODEL,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": temperature},
                }
                if schema is not None:
                    body["format"] = schema
                elif json_mode:
                    body["format"] = "json"
                response = requests.post(settings.OLLAMA_URL, json=body, timeout=timeout)
                response.raise_for_status()
                return response.json().get("response", "")

        except requests.RequestException as exc:
            last_error = exc
            if attempt < max_retries:
                time.sleep(1.5 * (attempt + 1))
                continue
            raise

    raise RuntimeError(f"LLM call failed: {last_error}")


def format_topics() -> str:
    return "\n".join(f"- {topic}: {TOPIC_DEFS[topic]}" for topic in TOPIC_KEYS)

def format_rubric(topic: str) -> str:
    rubric = SCORING_RUBRIC.get(topic, {})
    if not isinstance(rubric, dict):
        return ""
    return "\n".join(f"{score}: {description}" for score, description in sorted(rubric.items()))

def add_high_precision_topic_hints(comment: str, topics: list[str]) -> list[str]:
    text = comment.casefold()
    hinted_topics = list(topics)
    hint_patterns = {
        "Course organization and structure": [r"\borganiz(?:e|ed|ation|ing)\b", r"\bstructur(?:e|ed|ing)\b"],
        "Pace": [r"\bpace(?:d)?\b", r"\brushed?\b", r"\btoo (?:fast|slow)\b", r"\bnot enough time\b"],
        "Workload": [r"\bworkload\b", r"\btoo much work\b", r"\bmanageable workload\b", r"\boverwhelm(?:ed|ing)?\b"],
        "Student engagement and participation": [r"\bengag(?:e|ed|ing|ement)\b", r"\bparticipat(?:e|ed|ion)\b", r"\bdiscussion(?:s)?\b", r"\basking questions\b", r"\binteractive\b", r"\bclicker questions?\b"],
        "Clarity of explanations": [r"\bexplain(?:s|ed|ing|ation|ations)?\b", r"\bclear(?:ly)?\b", r"\beasy to understand\b", r"\bfollow along\b"],
        "Effectiveness of assignments": [r"\bassignments?\b", r"\bhomeworks?\b", r"\bproblem sets?\b", r"\bpractice (?:problems?|tasks?)\b", r"\bworksheets?\b", r"\bclicker questions?\b"],
        "Instructor's communication and availability": [r"\boffice hours\b", r"\bavailable\b", r"\bapproachable\b", r"\brespond(?:s|ed|ing)?\b", r"\bemails?\b", r"\bcommunicat(?:e|ed|ion|ive)\b"],
        "Learning resources and materials": [r"\bresources?\b", r"\bmaterials?\b", r"\bnotes?\b", r"\bslides?\b", r"\brecordings?\b", r"\breview sessions?\b", r"\bpractice exams?\b", r"\bstudy materials?\b"],
    }

    for topic, patterns in hint_patterns.items():
        if topic in hinted_topics:
            continue
        if any(re.search(pattern, text) for pattern in patterns):
            hinted_topics.append(topic)

    return hinted_topics

def sentiment_from_score(score: int) -> str:
    if score <= 2:
        return "negative"
    if score >= 4:
        return "positive"
    return "neutral"

def parse_optional_score(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, str):
        text = value.strip().lower()
        if text in {"", "null", "none", "n/a", "na"}:
            return None
        match = re.search(r"\b[1-5]\b", text)
        if not match:
            return None
        value = match.group(0)
    try:
        return max(1, min(5, int(value)))
    except (TypeError, ValueError):
        return None

def parse_confidence(value: Any) -> float:
    if value is None:
        return 0.0
    if isinstance(value, str):
        text = value.strip().lower()
        if text in {"", "null", "none", "n/a", "na"}:
            return 0.0
        percent_match = re.search(r"(\d+(?:\.\d+)?)\s*%", text)
        if percent_match:
            return max(0.0, min(1.0, float(percent_match.group(1)) / 100))
        number_match = re.search(r"\d+(?:\.\d+)?", text)
        if not number_match:
            return 0.0
        value = number_match.group(0)
    try:
        confidence = float(value)
    except (TypeError, ValueError):
        return 0.0
    if confidence > 1.0:
        confidence = confidence / 100
    return max(0.0, min(1.0, confidence))

def format_question_context(question: str | None) -> str:
    if not question:
        return ""
    return (
        "\n    SURVEY QUESTION THIS FEEDBACK ANSWERS (context only; judge what the feedback itself says):\n"
        f"    \"\"\"{truncate_example_text(question, 300)}\"\"\"\n"
    )

BOUNDARY_RULES = """- Organization: structure, sequencing, logistics, layout, scheduling, time management, course design.
    - Pace: fast/slow movement through material, rushing, keeping up, time pressure.
    - Workload: amount of work, burden, difficulty load, too much or manageable work.
    - Engagement: participation, discussion, questions, interactive work, activities.
    - Clarity: explanations, lectures, examples, understanding concepts.
    - Assignments: homework, practice tasks, worksheets, problem sets, usefulness of assigned work.
    - Atmosphere: sense of welcoming, belonging, comfort, motivation, stress, support.
    - Communication/availability: office hours, responsiveness, announcements, access to instructor.
    - Inclusivity/belonging: inclusion, accessibility, respect, feeling welcome across learners.
    - Assessment: exams, tests, quizzes, alignment, difficulty, fairness of assessment design.
    - Grading/feedback: grades, partial credit, grading policy, feedback on work.
    - Resources/materials: notes, slides, recordings, textbooks, review materials, posted resources."""

PACE_DIRECTIONS = ["too_fast", "too_slow", "appropriate"]

ANALYSIS_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "topics": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "topic": {"type": "string", "enum": list(TOPIC_KEYS)},
                    "score": {"type": ["integer", "null"]},
                    "confidence": {"type": "number"},
                    "evidence_quote": {"type": "string"},
                    "reasoning": {"type": "string"},
                    "direction": {"type": ["string", "null"], "enum": PACE_DIRECTIONS + [None]},
                },
                "required": ["topic", "score", "confidence", "evidence_quote", "reasoning", "direction"],
            },
        },
        "general_sentiment_score": {"type": ["integer", "null"]},
    },
    "required": ["topics", "general_sentiment_score"],
}

def format_all_rubrics() -> str:
    blocks = []
    for topic in TOPIC_KEYS:
        rubric = "\n".join(f"        {score}: {text}" for score, text in sorted(SCORING_RUBRIC.get(topic, {}).items()))
        blocks.append(f"    - {topic}: {TOPIC_DEFS[topic]}\n{rubric}")
    return "\n".join(blocks)

def format_scored_examples(examples: list[dict[str, Any]]) -> str:
    if not examples:
        return "[]"
    return json.dumps([{
        "feedback": truncate_example_text(str(example.get("feedback", ""))),
        "topic": example.get("topic"),
        "human_score": example.get("score", 3),
    } for example in examples], indent=2)

def analyze_comment(comment: str, classification_examples: list[dict[str, Any]] | None = None, sentiment_examples: list[dict[str, Any]] | None = None, model_choice: str = "local", question: str | None = None) -> dict[str, Any]:
    """One schema-enforced call that returns every topic in the comment with its rubric score."""
    topic_examples = retrieve_similar_examples(comment, classification_examples or [], limit=RAG_CLASSIFICATION_EXAMPLE_COUNT)
    score_examples = retrieve_similar_examples(comment, sentiment_examples or [], limit=RAG_CLASSIFICATION_EXAMPLE_COUNT + 1)

    prompt = f"""You are analyzing one course-evaluation comment written by a student.

    TOPICS, each with its 1-5 scoring rubric:
{format_all_rubrics()}

    BOUNDARY RULES:
    {BOUNDARY_RULES}

    SIMILAR HUMAN-CODED EXAMPLES (topics):
    {format_classification_examples(topic_examples)}

    SIMILAR HUMAN-SCORED EXAMPLES (topic, score):
    {format_scored_examples(score_examples)}
    Use the examples only to calibrate. Do not copy labels unless this feedback has similar concrete evidence.

    TASK:
    1. List every topic the feedback makes a SPECIFIC point about. Use the subject matter of the text.
       - Only include a topic when the feedback names something concrete that belongs to it (office hours or emails for
         Communication, explanations or examples for Clarity, exams for Assessment, discussions for Engagement, ...).
       - Personality praise alone ("caring", "kind", "passionate", "wants us to succeed", "approachable", "great teacher")
         is NOT Communication, Clarity, Engagement or Atmosphere. If that is all the feedback says, treat it as generic.
       - When unsure whether a topic applies, leave it out.
    2. For each topic, score it 1-5 with THAT topic's rubric, using only the part of the feedback about that topic.
       Use null for score when the topic is only named without any opinion (e.g. "Labs", "Videos").
    3. confidence: 0.0-1.0, how sure you are that the topic applies and the score is right.
    4. evidence_quote: a short exact phrase from the feedback. reasoning: at most 15 words.
    5. direction: for Pace only, "too_fast", "too_slow" or "appropriate"; null for every other topic.
    6. If the feedback is generic (no specific topic, e.g. "Great professor!"), return an empty topics list and set
       general_sentiment_score to 1-5 for its overall tone. Use null for neutral or irrelevant text ("N/A", "no comment").
       When topics are listed, general_sentiment_score is null.
    {format_question_context(question)}
    FEEDBACK:
    \"\"\"{comment}\"\"\"

    Return ONLY a JSON object with "topics" (list of {{topic, score, confidence, evidence_quote, reasoning, direction}}) and "general_sentiment_score".
    """

    last_error: Exception | None = None
    parsed = None
    for _attempt in range(MODEL_TASK_MAX_RETRIES):
        try:
            parsed = extract_json_object(call_llm(prompt, model_choice=model_choice, schema=ANALYSIS_SCHEMA))
            break
        except Exception as exc:
            last_error = exc
    if parsed is None:
        return {"status": "model_error", "reasoning": f"Failed to analyze with model after retries; last error: {last_error}", "topic_results": [], "general_score": None}

    topic_results = []
    seen_topics = set()
    for entry in parsed.get("topics") or []:
        if not isinstance(entry, dict):
            continue
        topic = str(entry.get("topic", "")).strip()
        if topic not in TOPIC_KEYS or topic in seen_topics:
            continue
        seen_topics.add(topic)
        score = parse_optional_score(entry.get("score"))
        direction = entry.get("direction") if topic == "Pace" and entry.get("direction") in PACE_DIRECTIONS else None
        evidence_quote = normalize_comment(str(entry.get("evidence_quote") or "")) or None
        topic_results.append((topic, {
            "topic_supported": True,
            "sentiment": sentiment_from_score(score) if isinstance(score, int) else "neutral",
            "score": score,
            "confidence": parse_confidence(entry.get("confidence")),
            "evidence_quote": evidence_quote,
            "reasoning": str(entry.get("reasoning") or "").strip(),
            "scoring_status": "scored",
            "direction": direction,
        }))

    general_score = parse_optional_score(parsed.get("general_sentiment_score")) if not topic_results else None
    return {"status": "classified", "reasoning": "", "topic_results": topic_results, "general_score": general_score}

def assess_comment_two_step(comment: str, classification_examples: list[dict[str, Any]], sentiment_examples: list[dict[str, Any]], model_choice: str, question: str | None) -> dict[str, Any]:
    """Older flow: one classification call, then one scoring call per topic. Same return shape as analyze_comment."""
    classification = classify_comment(comment, classification_examples=classification_examples, model_choice=model_choice, question=question)
    status = classification.get("classification_status", "classified")
    if status == "model_error":
        return {"status": status, "reasoning": classification.get("classification_reasoning", ""), "topic_results": [], "general_score": None}
    topic_results = []
    for topic in classification.get("topics", [OTHER]):
        if topic == OTHER:
            continue
        scored = score_comment_topic(comment, topic, sentiment_examples=sentiment_examples, model_choice=model_choice, question=question)
        scored.pop("is_mismatched", None)
        topic_results.append((topic, scored))
    return {"status": status, "reasoning": "", "topic_results": topic_results, "general_score": None}

def classify_comment(comment: str, classification_examples: list[dict[str, Any]] | None = None, model_choice: str = "local", question: str | None = None) -> dict[str, Any]:
    retrieved_examples = retrieve_similar_examples(comment, classification_examples or [], limit=RAG_CLASSIFICATION_EXAMPLE_COUNT)

    prompt = f"""You are classifying one course-evaluation comment into instructional topics.

    Categorization is strictly about the SUBJECT MATTER of the text. 
    Assign every topic that is mentioned.
    
    ALLOWED TOPICS:
    {format_topics()}
    - {OTHER}: Use this ONLY for completely generic praise ("Great class"), irrelevant text ("N/A"), or lists of nouns that contain absolutely no opinion (e.g., "lectures and extra credit quizzes"). Do not use this if the student expresses an observation.

    SIMILAR HUMAN-CODED EXAMPLES:
    {format_classification_examples(retrieved_examples)}

    HOW TO USE THE EXAMPLES:
    - Use examples only to calibrate boundaries and multi-topic style.
    - Do not copy labels unless this feedback has similar concrete evidence.

    BOUNDARY RULES:
    {BOUNDARY_RULES}

    Return ONLY valid JSON in this exact shape:
    {{
      "topics": ["Topic 1", "Topic 2"],
      "evidence": {{
        "Topic 1": "short exact phrase from feedback",
        "Topic 2": "short exact phrase from feedback"
      }}
    }}
    {format_question_context(question)}
    FEEDBACK:
    \"\"\"{comment}\"\"\"
    """

    last_error: Exception | None = None
    parsed = None
    for attempt in range(1, MODEL_TASK_MAX_RETRIES + 1):
        try:
            parsed = extract_json_object(call_llm(prompt, model_choice=model_choice))
            break
        except Exception as exc:
            last_error = exc

    if parsed is None:
        return {"topics": [OTHER], "classification_status": "model_error", "classification_reasoning": f"Failed to classify with model after retries; last error: {last_error}"}

    topics = parsed.get("topics", [OTHER])
    if not isinstance(topics, list):
        topics = [topics]

    evidence = parsed.get("evidence", {})
    evidence_by_topic = evidence if isinstance(evidence, dict) else {}
    valid_topics = []
    for topic in topics:
        if isinstance(topic, dict):
            topic = topic.get("topic") or topic.get("name")
        topic = str(topic).strip()
        if topic in TOPICS and topic not in valid_topics:
            valid_topics.append(topic)

    if not valid_topics:
        return {"topics": [OTHER], "classification_status": "classified"}
    if valid_topics == [OTHER]:
        return {"topics": [OTHER], "classification_status": "classified"}

    valid_topics = add_high_precision_topic_hints(comment, valid_topics)
    if len(valid_topics) > 1 and OTHER in valid_topics:
        valid_topics.remove(OTHER)

    return {"topics": valid_topics, "classification_status": "classified"}

def score_comment_topic(comment: str, topic: str, sentiment_examples: list[dict[str, Any]] | None = None, model_choice: str = "local", question: str | None = None) -> dict[str, Any]:
    retrieved_examples = retrieve_similar_examples(comment, sentiment_examples or [], limit=RAG_SENTIMENT_EXAMPLE_COUNT, topic=topic)
    prompt = f"""You are scoring one course-evaluation comment for one topic.

    Use the rubric exactly. The numeric score is rubric-specific, not generic sentiment.
    Score only the evidence that is relevant to the given TOPIC. Ignore praise or criticism about other topics.

    TOPIC: {topic}
    TOPIC DEFINITION: {TOPIC_DEFS.get(topic, topic)}

    RUBRIC:
    {format_rubric(topic)}

    RETRIEVED HUMAN-SCORED EXAMPLES FOR THIS SAME TOPIC:
    {format_sentiment_examples(retrieved_examples)}
    {format_question_context(question)}
    FEEDBACK:
    \"\"\"{comment}\"\"\"

    TASK:
    1. Decide whether the feedback is related to this exact topic.
    2. If the topic is completely unrelated, set topic_supported to false, score to null, sentiment to null.
    3. If the comment is just a noun without any opinion or observation (e.g., "Labs", "Videos"), set topic_supported to true, score to null, and sentiment to "neutral".
    4. If the comment expresses an opinion or observation (e.g., "super informative", "too fast", "doesn't give feedback"), assign the best matching integer rubric score from 1 to 5.
    5. Provide one short exact evidence quote from the feedback.
    6. Give one brief reason grounded in that evidence quote (Maximum 15 words). 
    7. Provide confidence from 0.0 to 1.0.

    Return ONLY valid JSON:
    {{
    "topic_supported": true,
    "sentiment": "positive|negative|neutral",
    "score": 1,
    "confidence": 0.0,
    "evidence_quote": "short exact quote from feedback",
    "reasoning": "brief explanation"
    }}
    If topic_supported is false, use JSON null for sentiment, score, and evidence_quote.
    """

    last_error: Exception | None = None
    for attempt in range(1, MODEL_TASK_MAX_RETRIES + 1):
        try:
            parsed = extract_json_object(call_llm(prompt, model_choice=model_choice))
            break
        except Exception as exc:
            last_error = exc
    else:
        return {"topic_supported": None, "sentiment": None, "score": None, "confidence": 0.0, "evidence_quote": None, "reasoning": "Failed to score with model after retries; excluded from averages.", "scoring_status": "model_error", "is_mismatched": False}

    try:
        raw_supported = parsed.get("topic_supported", True)
        if isinstance(raw_supported, bool):
            topic_supported = raw_supported
        else:
            topic_supported = str(raw_supported).strip().lower() not in {"false", "0", "no"}
        evidence_quote = parsed.get("evidence_quote")
        evidence_quote = normalize_comment(str(evidence_quote)) if evidence_quote else None
        score = parse_optional_score(parsed.get("score")) if topic_supported else None
        sentiment = str(parsed.get("sentiment", "")).strip().lower()
        if sentiment not in {"positive", "negative", "neutral"}:
            sentiment = None
        confidence = parse_confidence(parsed.get("confidence", 0.0))
        reasoning = str(parsed.get("reasoning", "")).strip()


        if topic_supported:
            if isinstance(score, int):
                sentiment = sentiment_from_score(score)
            else:
                if sentiment not in {"positive", "negative", "neutral"}:
                    sentiment = "neutral"
        else:
            score = None
            sentiment = None
            
        is_mismatched = not topic_supported
        
    except Exception as exc:
        return {"topic_supported": None, "sentiment": None, "score": None, "confidence": 0.0, "evidence_quote": None, "reasoning": "Failed to score with model; excluded from averages.", "scoring_status": "model_error", "is_mismatched": False}

    result = {
        "topic_supported": topic_supported,
        "sentiment": sentiment,
        "score": score,
        "confidence": confidence,
        "evidence_quote": evidence_quote,
        "reasoning": reasoning,
        "scoring_status": "scored",
        "is_mismatched": is_mismatched,
    }
    
    return result

def summarize_topic(topic: str, comments: list[dict[str, Any]], average_score: float | None, model_choice: str = "local") -> str:
    if not comments:
        return f"Summary of {topic}: No comments were assigned to this topic."
    if len(comments) == 1:
        return summarize_single_comment(topic, comments[0])

    scored_count = sum(1 for item in comments if isinstance(item.get("score"), int))
    model_error_count = sum(1 for item in comments if item.get("scoring_status") == "model_error")
    sentiment_counts = {sentiment: sum(1 for item in comments if item.get("sentiment") == sentiment) for sentiment in ("positive", "neutral", "negative")}
    
    scored_comments = [{
        "score": item.get("score"),
        "sentiment": item.get("sentiment"),
        "topic_supported": item.get("topic_supported"),
        "evidence_quote": item.get("evidence_quote"),
        "scoring_status": item.get("scoring_status", "unscored"),
        "text": item.get("feedback", ""),
    } for item in comments]
    
    exact_prefix = build_topic_summary_prefix(topic, len(comments), scored_count, average_score, sentiment_counts, model_error_count)
    
    prompt = f"""Summarize the course evaluation evidence for one topic.

    TOPIC: {topic}
    COMMENT COUNT: {len(comments)}
    SCORED COMMENT COUNT: {scored_count}
    AVERAGE SCORE: {average_score if average_score is not None else "N/A"}
    MODEL SCORING ERRORS: {model_error_count}
    SENTIMENT COUNTS:
    {json.dumps(sentiment_counts, indent=2)}
    RUBRIC:
    {format_rubric(topic) if topic != OTHER else "No rubric score for generic comments."}

    COMMENTS WITH SCORES:
    {json.dumps(scored_comments, indent=2)}

    Write 1 concise sentence of qualitative themes only.

    Rules:
    - Do not restate comment counts, sentiment counts, scores, averages, or percentages.
    - Refer to assigned comments, not students/respondents.
    - Do not mention a concern unless at least one listed comment states it.
    - Do not say "majority" unless the sentiment counts support it.
    - Do not repeat rubric dimensions unless the comments explicitly mention them.
    - Do not include meta-notes about following instructions.
    - Do not mention the absence of concerns as a concern.
    """

    try:
        summary = call_llm(prompt, model_choice=model_choice, temperature=0.2, timeout=120, json_mode=False).strip()
    except Exception as exc:
        return f"{exact_prefix} Themes unavailable due to model error."

    if not summary.startswith(f"Summary of {topic}:"):
        summary = f"Summary of {topic}: {summary}"
    cleaned = clean_topic_summary(topic, summary)
    body = cleaned.removeprefix(f"Summary of {topic}:").strip()
    return f"{exact_prefix} {body}" if body else exact_prefix

def summarize_single_comment(topic: str, comment: dict[str, Any]) -> str:
    feedback = normalize_comment(str(comment.get("feedback", "")))
    if len(feedback) > 180:
        feedback = feedback[:177].rstrip() + "..."
    score = comment.get("score")
    sentiment = comment.get("sentiment")
    if sentiment is None:
        sentiment = "unscored"
    score_text = f" with a score of {score}/5" if isinstance(score, int) else ""
    return f'Summary of {topic}: One assigned comment was {sentiment}{score_text}, citing: "{feedback}"'

def build_topic_summary_prefix(topic: str, comment_count: int, scored_count: int, average_score: float | None, sentiment_counts: dict[str, int], model_error_count: int = 0) -> str:
    if topic == OTHER:
        return f"Summary of {topic}: {comment_count} generic or uncategorized comments; excluded from rubric averages."

    score_text = f"average {average_score}/5" if average_score is not None else "no rubric average"
    prefix = f"Summary of {topic}: {comment_count} assigned comments; {scored_count} scored; {score_text}; {sentiment_counts.get('positive', 0)} positive, {sentiment_counts.get('neutral', 0)} neutral, {sentiment_counts.get('negative', 0)} negative."
    if model_error_count:
        prefix += f" {model_error_count} model scoring errors were excluded from averages."
    return prefix

def other_entry(feedback: str, classification_status: str, scoring_status: str, reasoning: str, question: str | None = None) -> dict[str, Any]:
    return {
        "feedback": feedback,
        "question": question,
        "sentiment": None,
        "score": None,
        "confidence": None,
        "classification_status": classification_status,
        "topic_supported": None,
        "evidence_quote": None,
        "scoring_status": scoring_status,
        "reasoning": reasoning,
    }

def public_comment(comment: dict[str, Any]) -> dict[str, Any]:
    return {
        "feedback": comment.get("feedback") or "",
        "classification_status": comment.get("classification_status") or "",
        "topic_supported": comment.get("topic_supported") if comment.get("topic_supported") is not None else "",
        "evidence_quote": comment.get("evidence_quote") or "",
        "sentiment": comment.get("sentiment") or "",
        "score": comment.get("score") if comment.get("score") is not None else "",
        "confidence": comment.get("confidence") if comment.get("confidence") is not None else "",
        "scoring_status": comment.get("scoring_status") or "",
        "reasoning": comment.get("reasoning") or "",
        "question": comment.get("question") or "",
        "direction": comment.get("direction") or "",
        "general_score": comment.get("general_score") if comment.get("general_score") is not None else "",
    }

def public_category(category: dict[str, Any]) -> dict[str, Any]:
    extra = {"direction_counts": category["direction_counts"]} if "direction_counts" in category else {}
    return {
        "topic": category["topic"],
        "average_score": category["average_score"],
        "comment_count": category["comment_count"],
        "scored_comment_count": category.get("scored_comment_count", 0),
        "reliability": category.get("reliability", ""),
        **extra,
        "comments": [public_comment(comment) for comment in category["comments"]],
    }

def public_category_score(category: dict[str, Any]) -> dict[str, Any]:
    return {
        "category": category["topic"],
        "average_score": category["average_score"],
        "comment_count": category["comment_count"],
    }

def clean_topic_summary(topic: str, summary: str) -> str:
    marker = f"Summary of {topic}:"
    text = summary.replace("\r\n", "\n").replace("\r", "\n").strip()
    marker_pattern = re.compile(rf"Summary\s+of\s+{re.escape(topic)}\s*:", re.IGNORECASE)
    marker_matches = list(marker_pattern.finditer(text))
    if marker_matches:
        text = text[marker_matches[-1].end():].strip()

    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\s*\n\s*", " ", text).strip()
    text = re.sub(r"(?i)\bNote:\s*.*$", "", text).strip()
    return f"{marker} {text}" if text else marker

def mean_score(scores: list[int | float]) -> float | None:
    return round(sum(scores) / len(scores), 2) if scores else None

def reliability_for_topic(comments: list[dict[str, Any]]) -> tuple[str, list[str]]:
    scored_count = sum(1 for item in comments if isinstance(item.get("score"), int))
    model_error_count = sum(1 for item in comments if item.get("scoring_status") == "model_error")
    low_confidence_count = sum(
        1 for item in comments
        if isinstance(item.get("score"), int)
        and isinstance(item.get("confidence"), (int, float))
        and item.get("confidence", 0.0) < LOW_CONFIDENCE_THRESHOLD
    )

    notes = []
    if scored_count == 0:
        notes.append("No scored rubric comments.")
    elif scored_count < MIN_RELIABLE_CATEGORY_COMMENTS:
        notes.append(f"Low sample: {scored_count} scored comments; use as directional evidence only.")
    if model_error_count:
        notes.append(f"{model_error_count} model scoring errors excluded from averages.")
    if low_confidence_count:
        notes.append(f"{low_confidence_count} low-confidence scored comments.")

    if scored_count == 0:
        return "unscored", notes
    if model_error_count:
        return "needs_review", notes
    if scored_count < MIN_RELIABLE_CATEGORY_COMMENTS:
        return "low_sample", notes
    if low_confidence_count:
        return "mixed_confidence", notes
    return "reliable", notes

def pluralize(count: int, singular: str, plural: str | None = None) -> str:
    word = singular if count == 1 else (plural or f"{singular}s")
    return f"{count} {word}"

def build_output_warnings(categories: list[dict[str, Any]], classification_error_count: int, failed_score_count: int, other_comment_count: int) -> list[str]:
    warnings = []
    low_sample_topics = [item["topic"] for item in categories if item["topic"] != OTHER and item.get("comment_count", 0) > 0 and item.get("reliability") in {"low_sample", "unscored"}]
    if low_sample_topics:
        warnings.append("Low-sample category scores should not be treated as stable professor metrics: " + ", ".join(low_sample_topics))
    if classification_error_count:
        verb = "was" if classification_error_count == 1 else "were"
        warnings.append(f"{pluralize(classification_error_count, 'feedback item')} failed classification and {verb} excluded from rubric scoring.")
    if failed_score_count:
        verb = "was" if failed_score_count == 1 else "were"
        warnings.append(f"{pluralize(failed_score_count, 'topic assignment')} failed scoring and {verb} excluded.")
    if other_comment_count:
        verb = "is" if other_comment_count == 1 else "are"
        warnings.append(f"{pluralize(other_comment_count, 'generic or uncategorized comment')} {verb} summarized but excluded from rubric averages.")
    return warnings

def write_combined_csv(output: dict[str, Any], csv_path: Path) -> None:
    rows = []
    summary_by_topic = {item["topic"]: item["summary"] for item in output.get("topic_summaries", []) if "topic" in item and "summary" in item}
    for topic_item in output["categories"]:
        topic = topic_item["topic"]
        topic_summary = summary_by_topic.get(topic, topic_item.get("summary", ""))
        comments = topic_item["comments"]
        if not comments:
            rows.append({
                "Course ID": output["course_id"],
                "Overall Score": output["overall_score"],
                "Topic": topic,
                "Topic Average Score": topic_item["average_score"],
                "Scored Comment Count": topic_item.get("scored_comment_count", 0),
                "Reliability": topic_item.get("reliability", ""),
                "Feedback": "",
                "Question": "",
                "Classification Status": "",
                "Topic Supported": "",
                "Evidence Quote": "",
                "Sentiment": "",
                "Score": "",
                "Confidence": "",
                "Scoring Status": "",
                "Reasoning": "",
                "Topic Summary": topic_summary,
            })
            continue

        for comment_idx, comment in enumerate(comments):
            rows.append({
                "Course ID": output["course_id"],
                "Overall Score": output["overall_score"],
                "Topic": topic,
                "Topic Average Score": topic_item["average_score"],
                "Scored Comment Count": topic_item.get("scored_comment_count", 0),
                "Reliability": topic_item.get("reliability", ""),
                "Feedback": comment["feedback"],
                "Question": comment.get("question", ""),
                "Classification Status": comment.get("classification_status", ""),
                "Topic Supported": comment.get("topic_supported", ""),
                "Evidence Quote": comment.get("evidence_quote", ""),
                "Sentiment": comment.get("sentiment", ""),
                "Score": comment.get("score", ""),
                "Confidence": comment.get("confidence", ""),
                "Scoring Status": comment.get("scoring_status", ""),
                "Reasoning": comment.get("reasoning", ""),
                "Topic Summary": topic_summary if comment_idx == 0 else "",
            })

    fieldnames = ["Course ID", "Overall Score", "Topic", "Topic Average Score", "Scored Comment Count", "Reliability", "Feedback", "Question", "Classification Status", "Topic Supported", "Evidence Quote", "Sentiment", "Score", "Confidence", "Scoring Status", "Reasoning", "Topic Summary"]
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

LIST_BULLETS = "•●○◦▪▫■□‣⁃∙·➢➤►▶✓✔�"

def strip_list_bullets(text: str) -> str:
    """Drop list bullets (exports often store them as the replacement character) and join items with "; "."""
    text = re.sub(rf"\n[ \t]*(?:[{re.escape(LIST_BULLETS)}*]|-(?=\s))[ \t]*", "; ", text)
    text = re.sub(rf"^[ \t]*(?:[{re.escape(LIST_BULLETS)}*]|-(?=\s))[ \t]*", "", text)
    text = re.sub(rf"[ \t]+[{re.escape(LIST_BULLETS)}][ \t]+", "; ", text)
    text = re.sub(r":\s*;\s*", ": ", text)
    return re.sub(r"(;\s*)+", "; ", text).replace("�", "'")

def prepare_comment_items(raw_comments: list[Any], dedupe_exact_comments: bool = True) -> tuple[list[dict[str, Any]], int]:
    """Accept plain strings or OCR responses ({"text", "question", "non_teaching_question"})."""
    items = []
    seen = set()
    duplicates = 0
    for raw in raw_comments:
        if isinstance(raw, dict):
            text = normalize_comment(strip_list_bullets(str(raw.get("text") or raw.get("feedback") or "")))
            question = normalize_comment(str(raw.get("question") or "")) or None
            non_teaching = bool(raw.get("non_teaching_question"))
        else:
            text, question, non_teaching = normalize_comment(strip_list_bullets(str(raw))), None, False
        if not text:
            continue
        if dedupe_exact_comments:
            if text in seen:
                duplicates += 1
                continue
            seen.add(text)
        items.append({"text": text, "question": question, "non_teaching_question": non_teaching})
    return items, duplicates

def analysis_pipeline(course_id: str, raw_comments: list[Any], output_dir: Path | None = None, write_files: bool = True, dedupe_exact_comments: bool = True, use_rag: bool = True, model_choice: str = "local", quantitative: list[dict[str, Any]] | None = None, extraction: dict[str, Any] | None = None, progress: Callable[[str, int, int], None] | None = None) -> dict[str, Any]:
    output_dir = output_dir or BASE_DIR / "results" / "combined"
    start_time = time.time()
    input_comment_count = len(raw_comments)
    items, duplicate_comments_removed = prepare_comment_items(raw_comments, dedupe_exact_comments)
    extraction = extraction or {}

    classification_examples = load_classification_examples() if use_rag else []
    sentiment_examples = load_sentiment_examples() if use_rag else []

    topic_comments: dict[str, list[dict[str, Any]]] = {topic: [] for topic in TOPICS}
    per_feedback_scores: dict[str, list[int]] = {}
    classification_error_count = 0
    failed_score_count = 0
    drop_counts = {"topic_unsupported": 0, "low_confidence": 0, "all_topics_rejected": 0}
    non_teaching_skipped = 0

    general_scores: list[int] = []
    pace_directions = {direction: 0 for direction in PACE_DIRECTIONS}

    def assess(item: dict[str, Any]) -> dict[str, Any]:
        try:
            if settings.PIPELINE_MODE == "two_step":
                return assess_comment_two_step(item["text"], classification_examples, sentiment_examples, model_choice, item["question"])
            return analyze_comment(item["text"], classification_examples, sentiment_examples, model_choice=model_choice, question=item["question"])
        except Exception as exc:  # never let one comment sink the whole report
            logger.exception("Assessment failed for one comment")
            return {"status": "model_error", "reasoning": f"Unexpected error: {exc}", "topic_results": [], "general_score": None}

    def notify(stage: str, done: int, total: int) -> None:
        if progress is not None:
            try:
                progress(stage, done, total)
            except Exception:
                logger.exception("Progress callback failed")

    # LLM calls run in parallel; results are then aggregated in the original comment order
    to_assess = [index for index, item in enumerate(items) if not item["non_teaching_question"]]
    assessments: dict[int, dict[str, Any]] = {}
    notify("comments", 0, len(to_assess))
    with ThreadPoolExecutor(max_workers=settings.max_parallel_calls(model_choice)) as pool:
        futures = {pool.submit(assess, items[index]): index for index in to_assess}
        for done, future in enumerate(as_completed(futures), 1):
            assessments[futures[future]] = future.result()
            notify("comments", done, len(to_assess))

    for index, item in enumerate(items):
        feedback, question = item["text"], item["question"]

        if item["non_teaching_question"]:
            # e.g. "Did you feel prepared by prior coursework?" answers describe the student, not the teaching
            non_teaching_skipped += 1
            topic_comments[OTHER].append(other_entry(feedback, "skipped_question", "not_applicable", "Answer to a survey question that is not about the teaching; not scored.", question))
            continue

        assessment = assessments[index]
        status = assessment["status"]

        if status == "model_error":
            classification_error_count += 1
            topic_comments[OTHER].append(other_entry(feedback, status, "classification_error", assessment["reasoning"], question))
            continue

        if not assessment["topic_results"]:
            entry = other_entry(feedback, status, "not_applicable", "Generic or non-actionable feedback; no rubric score assigned.", question)
            if isinstance(assessment["general_score"], int):
                entry["general_score"] = assessment["general_score"]
                general_scores.append(assessment["general_score"])
            topic_comments[OTHER].append(entry)
            continue

        passed_scoring_topics = 0
        for topic, scored in assessment["topic_results"]:
            # Check model errors before the confidence gate, because errors carry confidence 0.0
            if scored.get("scoring_status") == "model_error":
                failed_score_count += 1
                continue
            if scored.get("topic_supported") is False:
                drop_counts["topic_unsupported"] += 1
                continue
            threshold = CONFIDENCE_THRESHOLDS.get(topic, CONFIDENCE_THRESHOLDS["default"])
            if settings.CONFIDENCE_GATE and scored.get("confidence", 0) < threshold:
                drop_counts["low_confidence"] += 1
                continue

            score = scored.get("score")
            if isinstance(score, int):
                per_feedback_scores.setdefault(feedback, []).append(score)
            if topic == "Pace" and scored.get("direction") in pace_directions:
                pace_directions[scored["direction"]] += 1

            topic_comments[topic].append({"feedback": feedback, "question": question, "classification_status": status, **scored})
            passed_scoring_topics += 1

        if passed_scoring_topics == 0:
            drop_counts["all_topics_rejected"] += 1
            topic_comments[OTHER].append(other_entry(feedback, status, "not_applicable", "Model rejected specific topic during scoring phase; defaulted to Uncategorized.", question))

    topic_averages = {
        topic: mean_score([item["score"] for item in topic_comments[topic] if isinstance(item.get("score"), int)])
        for topic in TOPIC_KEYS
    }
    notify("summaries", 0, len(TOPICS))
    with ThreadPoolExecutor(max_workers=settings.max_parallel_calls(model_choice)) as pool:
        summary_futures = {
            topic: pool.submit(summarize_topic, topic, topic_comments[topic], topic_averages.get(topic), model_choice=model_choice)
            for topic in TOPICS
        }
        summaries = {}
        for done, topic in enumerate(TOPICS, 1):
            summaries[topic] = summary_futures[topic].result()
            notify("summaries", done, len(TOPICS))

    categories = []
    category_scores = []
    topic_summaries = []
    for topic in TOPIC_KEYS:
        comments = topic_comments[topic]
        scores = [item["score"] for item in comments if isinstance(item.get("score"), int)]
        average_score = topic_averages[topic]
        reliability, _ = reliability_for_topic(comments)
        summary = summaries[topic]
        categories.append({"topic": topic, "average_score": average_score, "comment_count": len(comments), "scored_comment_count": len(scores), "reliability": reliability, "comments": comments})
        if topic == "Pace":
            categories[-1]["direction_counts"] = pace_directions
        category_scores.append(public_category_score(categories[-1]))
        topic_summaries.append({"topic": topic, "summary": summary})

    other_summary = summaries[OTHER]
    categories.append({"topic": OTHER, "average_score": None, "comment_count": len(topic_comments[OTHER]), "scored_comment_count": 0, "reliability": "not_scored", "comments": topic_comments[OTHER]})
    topic_summaries.append({"topic": OTHER, "summary": other_summary})

    per_comment_score_means = [sum(scores) / len(scores) for scores in per_feedback_scores.values() if scores]
    overall_score = mean_score(per_comment_score_means)
    warnings = build_output_warnings(categories, classification_error_count=classification_error_count, failed_score_count=failed_score_count, other_comment_count=len(topic_comments[OTHER]))
    output = {
        "course_id": course_id,
        "model": model_choice,
        "overall_score": overall_score,
        "category_scores": category_scores,
        "topic_summaries": topic_summaries,
        "categories": [public_category(category) for category in categories],
        "quantitative": quantitative or [],
        # Tone of generic comments ("Great professor!") that fit no topic; kept apart from overall_score
        "general_sentiment": {
            "average_score": mean_score(general_scores),
            "scored_comments": len(general_scores),
            "positive": sum(1 for s in general_scores if s >= 4),
            "neutral": sum(1 for s in general_scores if s == 3),
            "negative": sum(1 for s in general_scores if s <= 2),
        },
        "metadata": {
            "input_comments": input_comment_count,
            "processed_comments": len(items),
            "non_teaching_skipped": non_teaching_skipped,
            "parser": extraction.get("parser", ""),
            "extraction_warnings": extraction.get("warnings", []),
            "duplicates_removed": duplicate_comments_removed,
            "scored_comments": len(per_comment_score_means),
            "generic_comments": len(topic_comments[OTHER]),
            "rag_enabled": use_rag,
            "model_id": settings.model_id_for(model_choice),
            "pipeline_mode": settings.PIPELINE_MODE,
            "confidence_gate": settings.CONFIDENCE_GATE,
            "prompt_version": settings.PROMPT_VERSION,
            "classification_errors": classification_error_count,
            "scoring_errors": failed_score_count,
            "dropped_topic_assignments": drop_counts,
            "warnings": warnings,
            "runtime_seconds": round(time.time() - start_time, 2),
        },
    }

    if write_files:
        output_dir.mkdir(parents=True, exist_ok=True)
        json_path = output_dir / f"{course_id}_COMBINED_REPORT.json"
        csv_path = output_dir / f"{course_id}_COMBINED_REPORT.csv"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2)
        write_combined_csv(output, csv_path)

    return output

def load_feedback_from_json(json_data: dict[str, Any]) -> tuple[str, list[str]]:
    course_id = json_data.get("course_id", "UNKNOWN")
    raw_comments = json_data.get("raw_comments", [])
    if not isinstance(raw_comments, list):
        raise ValueError("raw_comments must be a list")
    return course_id, raw_comments

if __name__ == "__main__":
    json_input = {
        "course_id": "TEST_THREE",
        "raw_comments": ["I appreciate how open he is and how he makes so much time for us to communicate and talk to him. He hosts coffee hours which is a time where students can just converse with him and it was refreshing to see because it shows that he cares about his student's success and is curious about how they are doing. He is very down to earth and is very considerate about his students."]
    }
    course_id, raw_comments = load_feedback_from_json(json_input)
    output = analysis_pipeline(course_id, raw_comments)
    output_path = BASE_DIR / "results" / "TEST_THREE.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)