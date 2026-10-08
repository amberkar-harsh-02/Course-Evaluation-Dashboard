from __future__ import annotations
import csv
import json
import re
import time
import os
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any
import requests
from data import SCORING_RUBRIC, TOPIC_DEFS, TOPIC_KEYS
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parents[0]
OTHER = "None of the above / Other"
TOPICS = list(TOPIC_KEYS) + [OTHER]

OLLAMA_URL = "http://10.9.144.10:8001/api/generate"
MODEL = "qwen35b:latest"

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

TOPIC_EVIDENCE_PATTERNS = {
    "Course organization and structure": [r"\borganiz(?:e|ed|ation|ing)\b", r"\bstructure(?:d)?\b", r"\bschedul(?:e|ed|ing)\b", r"\bsequenc(?:e|ed|ing)\b", r"\bnavigation\b", r"\boriginally specified\b"],
    "Pace": [r"\bpace(?:d)?\b", r"\bfast\b", r"\bslow\b", r"\brushed?\b", r"\btoo quickly\b", r"\bkeep up\b", r"\btime constraint\b", r"\bnot enough time\b", r"\bmore time\b", r"\bdo not have much time\b", r"\bbefore the final\b"],
    "Workload": [r"\bworkload\b", r"\bamount of work\b", r"\btoo much work\b", r"\bmanageable workload\b", r"\btime burden\b", r"\bconsume(?:d)? too much\b", r"\boverwhel(?:m|med|ming)\b", r"\bpacked.*full\b", r"\btoo many.*assignments\b", r"\bcan't keep up\b", r"\bburden\b", r"\btoo much to handle\b"],
    "Student engagement and participation": [r"\bengag(?:e|ed|ing|ement)\b", r"\bengaging lecturer\b", r"\bengaging lectures?\b", r"\bparticipat(?:e|ed|ion)\b", r"\bdiscussion\b", r"\bencourag(?:e|ed|es|ing) discussion\b", r"\bask(?:ing)? questions\b", r"\bgo over any question\b", r"\bquestions? .* lecture\b", r"\bfeel free to ask\b", r"\binteractive\b", r"\bclicker questions?\b", r"\bclickers?\b", r"\bworksheets?\b", r"\boffice hours\b"],
    "Clarity of explanations": [r"\bclear(?:ly)?\b", r"\bexplain(?:s|ed|ing|ation|ations)?\b", r"\bunderstand(?:able|ing)?\b", r"\bunderstood\b", r"\bfollow along\b", r"\bmanageable\b", r"\bdigestible\b", r"\bstraightforward\b", r"\bbreak(?:ing)? down\b", r"\beasy to understand\b", r"\bmade .* understandable\b", r"\bmade .* doable\b", r"\btaught really well\b"],
    "Effectiveness of assignments": [r"\bassignments?\b", r"\bhomeworks?\b", r"\bproblem sets?\b", r"\bpractice problems?\b", r"\bexample problems?\b", r"\bworksheets?\b", r"\bclicker questions?\b", r"\bclickers? were helpful\b", r"\bgave me an idea of what exam questions\b"],
    "Classroom atmosphere": [r"\batmosphere\b", r"\benvironment\b", r"\bwelcom(?:e|ing)\b", r"\bsupportive\b", r"\bcomfortable\b", r"\bdemotivating\b", r"\bstressful environment\b", r"\benergy\b", r"\bvibe\b", r"\bintimidating\b", r"\brelaxed\b", r"\btone of the class\b"],
    "Instructor's communication and availability": [r"\bcommunicat(?:e|ed|ion|ive)\b", r"\brespond(?:s|ed|ing)?\b", r"\bemails?\b", r"\bdiscussion posts?\b", r"\boffice hours\b", r"\bavailable\b", r"\bapproachable\b", r"\bset aside time\b", r"\bmeet with\b", r"\btakes? the time\b", r"\bgo over any question\b", r"\bup to date\b", r"\breminders?\b", r"\baccommodations?\b"],
    "Inclusivity and sense of belonging": [r"\binclus(?:ive|ion|ivity)\b", r"\bbelonging\b", r"\bwelcom(?:e|ed|ing)\b", r"\baccessible\b", r"\blearning styles?\b", r"\brespect(?:ful|ed)?\b", r"\bcatering\b"],
    "Assessment": [r"\bassessments?\b", r"\bexams?\b", r"\btests?\b", r"\bquizzes?\b", r"\bmidterms?\b", r"\bfinal\b", r"\bexam questions?\b"],
    "Grading and feedback": [r"\bgrad(?:e|ed|es|ing)\b", r"\bgrading system\b", r"\bpartial credit\b", r"\bfeedback\b", r"\bredemption\b", r"\bgrade policy\b"],
    "Learning resources and materials": [r"\bresources?\b", r"\bmaterials?\b", r"\bnotes?\b", r"\bslides?\b", r"\bpower\s*points?\b", r"\bbruin\s*cast\b", r"\brecordings?\b", r"\breview sessions?\b", r"\bposted online\b", r"\bccle\b", r"\blecture notes?\b", r"\bstudy materials?\b", r"\bflashcards?\b", r"\bpractice exams?\b"],
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


def call_llm(prompt: str, model_choice: str = "local", temperature: float = 0.1, timeout: int = 90, max_retries: int = LLM_MAX_RETRIES) -> str:
    last_error: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            if model_choice == "openai":
                api_key = os.environ.get("OPENAI_API_KEY", "").strip()
                
                openai_timeout = max(timeout, 180)
                
                response = requests.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                    json={
                        "model": "gpt-5.6-terra",
                        "messages": [{"role": "user", "content": prompt}],
                        "reasoning_effort": "low", 
                    },
                    timeout=openai_timeout,
                )
                response.raise_for_status()
                return response.json()["choices"][0]["message"]["content"]
                
            elif model_choice == "anthropic":
                api_key = os.environ.get("ANTHROPIC_API_KEY", "")
                response = requests.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={
                        "x-api-key": api_key,
                        "anthropic-version": "2023-06-01",
                        "content-type": "application/json"
                    },
                    json={
                        "model": "claude-sonnet-4-6", # <-- Sonnet 4.6
                        "messages": [{"role": "user", "content": prompt + "\n\nRespond strictly with JSON format."}],
                        "max_tokens": 1024,
                        "temperature": temperature,
                    },
                    timeout=timeout,
                )
                response.raise_for_status()
                return response.json()["content"][0]["text"]
                
            else:
                # Default Local Mac Studio Ollama Connection
                response = requests.post(
                    OLLAMA_URL,
                    json={
                        "model": MODEL,
                        "prompt": prompt,
                        "stream": False,
                        "format": "json",
                        "temperature": temperature,
                    },
                    timeout=timeout,
                )
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

def has_topic_evidence(comment: str, topic: str) -> bool:
    if topic == OTHER:
        return True
    patterns = TOPIC_EVIDENCE_PATTERNS.get(topic, [])
    text = comment.casefold()
    return any(re.search(pattern, text) for pattern in patterns)

def evidence_quote_is_grounded(evidence_quote: str | None, comment: str) -> bool:
    if not evidence_quote:
        return False
    cleaned_quote = str(evidence_quote).strip().casefold()
    if cleaned_quote in {"", "null", "none", "n/a", "false"}:
        return False
    return True

def looks_like_generic_only_comment(comment: str) -> bool:
    if any(has_topic_evidence(comment, topic) for topic in TOPIC_KEYS):
        return False

    tokens = retrieval_tokens(comment)
    if len(tokens) > 15:
        return False

    text = comment.casefold()
    concrete_keywords = ["assign", "exam", "lecture", "class", "material", "discussion", "grade", "feedback", "office", "resource", "classroom", "pace", "workload", "assessment", "quiz", "test"]
    has_concrete = any(kw in text for kw in concrete_keywords)
    if not has_concrete and len(tokens) < 8:
        return True

    generic_patterns = [
        r"\b(best|great|excellent|amazing|incredible|fantastic|good|wonderful|outstanding|awesome)\b.*\b(professor|instructor|teacher|lecturer)\b",
        r"\b(professor|instructor|teacher|lecturer)\b.*\b(best|great|excellent|amazing|incredible|fantastic|good|wonderful|outstanding|awesome)\b",
        r"\b(no complaints|love this class|goat)\b",
    ]
    return any(re.search(pattern, text) for pattern in generic_patterns)

def filter_topics_by_evidence(comment: str, topics: list[str], mode: str = "soft") -> list[str]:
    valid_topics = []
    
    for topic in topics:
        if topic in TOPICS and topic not in valid_topics:
            valid_topics.append(topic)

    if not valid_topics:
        return [OTHER]

    if len(valid_topics) > 1 and OTHER in valid_topics:
        valid_topics.remove(OTHER)

    return valid_topics


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

# 🚀 NEW: Added model_choice
def classify_with_llama(comment: str, classification_examples: list[dict[str, Any]] | None = None, evidence_filter_mode: str = "soft", model_choice: str = "local") -> dict[str, Any]:
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
    - Organization: structure, sequencing, logistics, layout, scheduling, time management, course design.
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
    - Resources/materials: notes, slides, recordings, textbooks, review materials, posted resources.

    Return ONLY valid JSON in this exact shape:
    {{
      "topics": ["Topic 1", "Topic 2"],
      "evidence": {{
        "Topic 1": "short exact phrase from feedback",
        "Topic 2": "short exact phrase from feedback"
      }}
    }}

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

    filtered = filter_topics_by_evidence(comment, valid_topics, mode=evidence_filter_mode)

    return {"topics": filtered, "classification_status": "classified"}

# 🚀 NEW: Added model_choice
def sentiment_with_llama(comment: str, topic: str, sentiment_examples: list[dict[str, Any]] | None = None, model_choice: str = "local") -> dict[str, Any]:
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

def check_topic_mismatch(reasoning: str, topic: str) -> bool:
    text = reasoning.lower()
    critical_patterns = [
        r"but\s+there\s+is\s+no\s+(?:explicit\s+)?",
        r"but\s+no\s+(?:explicit\s+)?",
        r"(?:only\s+)?mentions?\s+.*(?:not|but\s+not)\s+",
        r"(?:doesn't|does\s+not)\s+(?:explicitly\s+)?mention",
        r"(?:doesn't|does\s+not)\s+(?:explicitly\s+)?discuss",
        r"(?:doesn't|does\s+not)\s+(?:explicitly\s+)?address",
        r"implies\s+.*but\s+(?:doesn't|does\s+not)",
        r"mentions\s+.*but\s+(?:doesn't|does\s+not|isn't)",
    ]
    standard_patterns = [
        r"does not\s+(?:explicitly\s+)?praise",
        r"does not\s+(?:explicitly\s+)?criticize",
        r"does not\s+(?:explicitly\s+)?relate",
        r"no\s+(?:explicit\s+)?evidence",
        r"not\s+(?:explicitly\s+)?specific",
        r"unrelated",
        r"cannot determine",
        r"not\s+(?:directly\s+)?relevant",
        r"tangential\s+to",
        r"no\s+evidence\s+(?:about|of)",
        r"comment\s+(?:doesn't|does not|couldn't|could not)\s+address",
    ]
    all_patterns = critical_patterns + standard_patterns
    for pattern in all_patterns:
        if re.search(pattern, text):
            return True
    return False

# 🚀 NEW: Added model_choice
def summarize_topic_with_llama(topic: str, comments: list[dict[str, Any]], average_score: float | None, model_choice: str = "local") -> str:
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
        summary = call_llm(prompt, model_choice=model_choice, temperature=0.2, timeout=120).strip()
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
    }

def public_category(category: dict[str, Any]) -> dict[str, Any]:
    return {
        "topic": category["topic"],
        "average_score": category["average_score"],
        "comment_count": category["comment_count"],
        "scored_comment_count": category.get("scored_comment_count", 0),
        "reliability": category.get("reliability", ""),
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

    fieldnames = ["Course ID", "Overall Score", "Topic", "Topic Average Score", "Scored Comment Count", "Reliability", "Feedback", "Classification Status", "Topic Supported", "Evidence Quote", "Sentiment", "Score", "Confidence", "Scoring Status", "Reasoning", "Topic Summary"]
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

# 🚀 NEW: Added model_choice
def analysis_pipeline(course_id: str, raw_comments: list[str], output_dir: Path | None = None, write_files: bool = True, dedupe_exact_comments: bool = True, use_rag: bool = True, evidence_filter_mode: str = "soft", model_choice: str = "local") -> dict[str, Any]:
    output_dir = output_dir or BASE_DIR / "results" / "combined"
    start_time = time.time()
    input_comment_count = len(raw_comments)
    duplicate_comments_removed = 0

    if dedupe_exact_comments:
        raw_comments, duplicate_comments_removed = dedupe_comments(raw_comments)

    classification_examples = load_classification_examples() if use_rag else []
    sentiment_examples = load_sentiment_examples() if use_rag else []

    topic_comments: dict[str, list[dict[str, Any]]] = {topic: [] for topic in TOPICS}
    per_feedback_scores: dict[str, list[int]] = {}
    classification_error_count = 0
    failed_score_count = 0

    for idx, feedback in enumerate(raw_comments, 1):
        classification = classify_with_llama(feedback, classification_examples=classification_examples, evidence_filter_mode=evidence_filter_mode, model_choice=model_choice)
        topics = classification.get("topics", [OTHER])
        classification_status = classification.get("classification_status", "classified")
        classification_reasoning = classification.get("classification_reasoning", "")
        if classification_status == "model_error":
            classification_error_count += 1

        passed_scoring_topics = 0 

        for topic in topics:
            if topic == OTHER:
                if classification_status == "model_error":
                    continue
                scoring_status = "classification_error" if classification_status == "model_error" else "not_applicable"
                reasoning = classification_reasoning if classification_status == "model_error" else "Generic or non-actionable feedback; no rubric score assigned."
                topic_comments[OTHER].append({"feedback": feedback, "sentiment": None, "score": None, "confidence": None, "classification_status": classification_status, "topic_supported": None, "evidence_quote": None, "scoring_status": scoring_status, "reasoning": reasoning})
                passed_scoring_topics += 1
                continue

            scored = sentiment_with_llama(feedback, topic, sentiment_examples=sentiment_examples, model_choice=model_choice)
            is_mismatched = scored.pop("is_mismatched", False)
            threshold = CONFIDENCE_THRESHOLDS.get(topic, CONFIDENCE_THRESHOLDS["default"])
            unsupported_topic = scored.get("topic_supported") is False
            
            if unsupported_topic or scored.get("confidence", 0) < threshold:
                continue
            
            score = scored.get("score")
            if isinstance(score, int):
                per_feedback_scores.setdefault(feedback, []).append(score)
            elif scored.get("scoring_status") == "model_error":
                failed_score_count += 1
                continue
            

            topic_comments[topic].append({"feedback": feedback, "classification_status": classification_status, **scored})
            passed_scoring_topics += 1

        if passed_scoring_topics == 0:
            topic_comments[OTHER].append({
                "feedback": feedback,
                "sentiment": None,
                "score": None,
                "confidence": None,
                "classification_status": classification_status,
                "topic_supported": None,
                "evidence_quote": None,
                "scoring_status": "not_applicable",
                "reasoning": "Model rejected specific topic during scoring phase; defaulted to Uncategorized."
            })

    categories = []
    category_scores = []
    topic_summaries = []
    for topic in TOPIC_KEYS:
        comments = topic_comments[topic]
        scores = [item["score"] for item in comments if isinstance(item.get("score"), int)]
        average_score = mean_score(scores)
        reliability, _ = reliability_for_topic(comments)
        summary = summarize_topic_with_llama(topic, comments, average_score, model_choice=model_choice)
        categories.append({"topic": topic, "average_score": average_score, "comment_count": len(comments), "scored_comment_count": len(scores), "reliability": reliability, "comments": comments})
        category_scores.append(public_category_score(categories[-1]))
        topic_summaries.append({"topic": topic, "summary": summary})

    other_summary = summarize_topic_with_llama(OTHER, topic_comments[OTHER], None, model_choice=model_choice)
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
        "metadata": {
            "input_comments": input_comment_count,
            "processed_comments": len(raw_comments),
            "duplicates_removed": duplicate_comments_removed,
            "scored_comments": len(per_comment_score_means),
            "generic_comments": len(topic_comments[OTHER]),
            "rag_enabled": use_rag,
            "evidence_filter_mode": evidence_filter_mode,
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