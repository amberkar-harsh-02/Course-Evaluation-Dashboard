"""Turn course-evaluation exports into whole student responses plus rating tables.

Every extractor returns the same shape:

    {
        "parser": "tabular-export" | "report-table" | "pdf" | "docx",
        "responses": [{"question": str | None, "text": str}, ...],   # one entry per student answer
        "quantitative": [{"question", "n", "mean", "distribution": {label: count}}, ...],
        "warnings": [str, ...],
    }

Responses are kept whole: a multi-sentence answer stays one item, and wrapped lines are joined
back together. The survey question each answer belongs to is kept when it can be found.
"""
from __future__ import annotations

import io
import logging
import re
import unicodedata
from pathlib import Path
from typing import Any

import pandas as pd

logger = logging.getLogger("ocr.extractors")

BASE_DIR = Path(__file__).resolve().parent

# ---------------------------------------------------------------------------
# Noise rules (carried over from the original gatekeeper, applied per response now)
# ---------------------------------------------------------------------------
SQUISHED_BLACKLIST = {
    "needsimprovement", "excellent", "good", "fair", "poor",
    "stronglyagree", "agree", "neutral", "disagree", "stronglydisagree",
    "notapplicable", "na", "yes", "no", "quantitative", "qualitative",
    "outstanding", "satisfactory", "unsatisfactory", "dna", "sd", "m", "n",
    "reportcomments", "none", "verygood", "learningoutcomes", "assignments",
    "duedates", "grading", "aboutright", "toomuch", "toolittle",
    "morethan", "lessthan", "to", "or", "-", "notevenneeded", "responses", "comments",
}

SUBSTRING_BLACKLIST = [
    "students enrolled", "students responded", "response rate", "response ratio", "response count",
    "invited count", "individual instructor report", "report comments", "please find your instructor summary",
    "this report is unique to a teacher", "the response statistics at the top", "course and teacher response rates",
    "student qualitative response (raw comment text)", "category question header", "statistics value",
    "created monday", "created tuesday", "created wednesday", "created thursday", "created friday",
    "created saturday", "created sunday", "courses audience", "teachers audience",
    "question personalization", "sections represented in this data", "if the class sections have been merged",
    "sometimes students respond",
]

REGEX_BLACKLIST = [
    r"^page\s+\d+(\s*(of|/)\s*\d+)?$",
    r"page \d+/\d+$",
    r"^\d{2}-(spring|fall|winter|summer)\b",
    r"^(spring|fall|winter|summer) \d{4}$",
    r"^(cst|chem|bio|chm)\s*\d+[a-z]?\s*\(\d+",
    r"^[\d\s.,%|()/-]+$",                               # numbers, percentages, separators only
    r"^(total|raters|responded|invited|statistics|value)\b[\s\d.%/|]*$",
    r"\bn=\d+\b.*\bav\.?=",                             # "Excellent n=168 av.=.21 md= dev.=0.74"
    r"\b\d+\s+\d+(\.\d+)?%$",                           # rating rows: "7-9 hours 16 39.02%"
    r"^\d+\s*-\s*[a-z].*,\s*\d+\s*-",                   # scale legends: "1 - Low, 2 - Medium, 3 - High"
    r"^(mean|median|mode|standard deviation|std\.? dev\.?|variance|count)\b[\s:]*[\d.]+$",
    r"\d+(\.\d+)?%(\s+[\d.]+){2,}$",                    # rating rows with stats after the percentage
    r"^response table\b",
    r"^(more|less) than \d+$",
    r"^(for )?additional information\.?$",
    r"^(high|low|excellent|very good|good|fair|poor|outstanding|satisfactory|unsatisfactory|needs improvement|"
    r"too much|too little|about right|neutral|strongly agree|agree|disagree|strongly disagree|n/a|na|dna|m|sd|n|\s|/)+$",
]

NO_ANSWER = {
    "n/a", "na", "none", "nope", "no", "nothing", "no comment", "no comments", "nothing else", "not applicable",
    "nothing to add", "no thanks", "nah", "nope!", "none.", "n/a.", "no.", "nothing.", ".", "-", "idk", "no response",
}

SCALE_WORDS = {
    "outstanding": 5, "very good": 4, "satisfactory": 3, "needs improvement": 2, "unsatisfactory": 1,
    "strongly agree": 5, "agree": 4, "neutral": 3, "disagree": 2, "strongly disagree": 1,
    "excellent": 5, "good": 4, "fair": 3, "poor": 2,
    "not applicable": None, "about right": None, "too much": None, "too little": None,
}

QUESTION_START = re.compile(
    r"^(\d+\.\s+|q\d+[_.:]?\s*)?(please|assess|describe|what|how|why|did|do you|does|is there|are there|were|was there|"
    r"comments|class assignments|class materials|classroom activities|for the number|you may|if appropriate|"
    r"to what extent|identify|explain|list|in what ways)\b",
    re.IGNORECASE,
)

PERCENT_CELL = re.compile(r"^(\d+(?:\.\d+)?)%\s*\((\d+)\)$")

# Headers of rating (multiple-choice) sections; written comments never belong to these
RATING_SECTION = re.compile(
    r"to what extent do you feel|what requirements does this course|questions focused on|"
    r"your view of course characteristics|background information|year in school|ucla gpa|expected grade",
    re.IGNORECASE,
)

PROMPT_START = re.compile(r"^(\d+\.\s+)?please (identify|describe|provide|explain|list|comment|restate|share)\b", re.IGNORECASE)

# Answers to these questions are about the student, not the teaching
NON_TEACHING_QUESTION = re.compile(
    r"did you feel prepared|prior coursework|high school|class standing|year in school|gpa|expected grade|"
    r"why are you taking|requirements does this course fulfill|select your ta",
    re.IGNORECASE,
)

_gatekeeper: tuple[Any, Any] | None = None
_gatekeeper_loaded = False


def load_gatekeeper() -> tuple[Any, Any] | None:
    """TF-IDF + LinearSVC noise classifier from train_model.py, loaded once."""
    global _gatekeeper, _gatekeeper_loaded
    if _gatekeeper_loaded:
        return _gatekeeper
    _gatekeeper_loaded = True
    try:
        import joblib
        _gatekeeper = (
            joblib.load(BASE_DIR / "comment_classifier.pkl"),
            joblib.load(BASE_DIR / "tfidf_vectorizer.pkl"),
        )
        logger.info("ML gatekeeper loaded")
    except Exception as exc:  # the rule filters still work without it
        logger.warning("ML gatekeeper not available (%s); using rule filters only", exc)
        _gatekeeper = None
    return _gatekeeper


# ---------------------------------------------------------------------------
# Text helpers
# ---------------------------------------------------------------------------
BULLET_CHARS = "•●○◦▪▫■□‣⁃∙·➢➤►▶✓✔�"
_LINE_BULLET = rf"(?:[{re.escape(BULLET_CHARS)}*]|-(?=\s))"


def strip_bullets(text: str) -> str:
    """Remove list bullets from an answer: bulleted lines are joined with "; " instead.

    Exports often store a bullet as "�" (the replacement character); inside a word
    ("wouldn�t") it is an apostrophe and is left for clean_text to fix.
    """
    text = re.sub(rf"\n[ \t]*{_LINE_BULLET}[ \t]*", "; ", text)              # bullet starting a new line
    text = re.sub(rf"^[ \t]*{_LINE_BULLET}[ \t]*", "", text)                  # bullet at the very start
    text = re.sub(rf"[ \t]+[{re.escape(BULLET_CHARS)}][ \t]+", "; ", text)    # bullet between items on one line
    text = re.sub(r":\s*;\s*", ": ", text)                                     # "Strengths:; good pace" -> "Strengths: good pace"
    return re.sub(r"(;\s*)+", "; ", text)


def clean_text(text: Any) -> str:
    text = unicodedata.normalize("NFKC", str(text)).replace("\x00", "")
    text = strip_bullets(text).replace("�", "'")
    text = re.sub(r"([a-z])- ([a-z])", r"\1\2", text)     # "instruc- tor" -> "instructor"
    return re.sub(r"\s+", " ", text).strip()


def squish(text: str) -> str:
    return re.sub(r"[\s\-‐_|]", "", text.lower())


def is_noise(text: str) -> bool:
    lower = text.lower().strip()
    if not lower or lower == "nan":
        return True
    if squish(lower) in SQUISHED_BLACKLIST:
        return True
    if any(bad in lower for bad in SUBSTRING_BLACKLIST):
        return True
    return any(re.search(pattern, lower) for pattern in REGEX_BLACKLIST)


def is_question(text: str) -> bool:
    s = re.sub(r"\s*\((maximum|max\.?)[^)]*\)$", "", text.strip(), flags=re.IGNORECASE)
    if len(s) > 400:
        return False
    if PROMPT_START.match(s) and len(s) > 40:
        return True
    ends_like_prompt = s.endswith((":", ": -", ":-", "?", " -"))
    numbered = re.match(r"^\d+\.\s+\S", s)
    if numbered and QUESTION_START.match(s) and (ends_like_prompt or s.endswith(".") or "?" in s):
        return True
    return ends_like_prompt and (bool(QUESTION_START.match(s)) or s.endswith(": -"))


def is_numbered_item(text: str) -> bool:
    """Numbered survey items that are not open questions, e.g. "5. The instructor used course time effectively." """
    return bool(re.match(r"^\d+\.\s+\S", text.strip())) and not is_question(text)


_english_words: set[str] | None = None


def english_ratio(text: str) -> float:
    """Share of words that are real English words; garbage from broken PDF fonts scores near 0."""
    global _english_words
    if _english_words is None:
        try:
            import wordninja
            _english_words = set(wordninja.DEFAULT_LANGUAGE_MODEL._wordcost)
        except Exception:
            _english_words = set()
    visible = re.sub(r"\s", "", text)
    if visible and sum(ch.isalpha() for ch in visible) / len(visible) < 0.6:
        return 0.0  # mostly symbols, e.g. "<--!-- A()# %$-*#)+*(#B-"
    tokens = [t.lower() for t in re.findall(r"[A-Za-z]+", text) if len(t) >= 3]
    if not tokens:
        return 1.0 if len(visible) <= 3 else 0.0
    if not _english_words:
        return 1.0
    return sum(t in _english_words for t in tokens) / len(tokens)


def is_garbage(text: str) -> bool:
    return english_ratio(text) < 0.6


def is_no_answer(text: str) -> bool:
    return text.lower().strip(" !.") in {a.strip(" !.") for a in NO_ANSWER}


def ends_sentence(text: str) -> bool:
    return bool(re.search(r"[.!?)\"”']$", text.strip()))


def keep_response(text: str, use_gatekeeper: bool) -> bool:
    if is_noise(text) or is_no_answer(text) or is_question(text):
        return False
    if len(text.split()) < 2:
        return False
    if not use_gatekeeper:
        return True
    gatekeeper = load_gatekeeper()
    if gatekeeper is None:
        return True
    classifier, vectorizer = gatekeeper
    try:
        features = vectorizer.transform([text])
        return features.nnz == 0 or classifier.decision_function(features)[0] > -0.8
    except Exception as exc:
        logger.warning("Gatekeeper failed on a response (%s); keeping it", exc)
        return True


def scale_value(label: str) -> int | None:
    return SCALE_WORDS.get(re.sub(r"[\s-]+", " ", label.lower()).replace("improve ment", "improvement").strip())


def make_result(parser: str) -> dict[str, Any]:
    return {"parser": parser, "responses": [], "quantitative": [], "warnings": [], "garbage_dropped": 0}


# ---------------------------------------------------------------------------
# Tabular exports: one row per student, one column per question
# ---------------------------------------------------------------------------
META_COLUMN = re.compile(r"subjectid|enrollment|filloutdate|date|time|timestamp|^sheet$|source of dataset|^id$", re.I)


def clean_question_header(header: str) -> str:
    header = clean_text(header)
    header = re.sub(r"^Q\d+_", "", header)
    parts = [p.strip() for p in header.split("_") if p.strip()]
    unique_parts: list[str] = []
    for part in parts:
        if part not in unique_parts:
            unique_parts.append(part)
    return " — ".join(unique_parts) if unique_parts else header


def is_free_text_column(values: pd.Series) -> bool:
    values = values.dropna().astype(str).str.strip()
    values = values[values != ""]
    if len(values) < 3:
        return False
    if values.str.fullmatch(r"[\d.\-/: ]+").mean() > 0.5:
        return False
    unique_ratio = values.nunique() / len(values)
    return values.str.len().median() >= 12 and unique_ratio >= 0.3


def looks_like_tidy_export(df: pd.DataFrame) -> bool:
    if df.shape[0] < 3 or df.shape[1] < 3:
        return False
    header_text = [str(c) for c in df.columns]
    unnamed = sum(h.startswith("Unnamed") for h in header_text)
    if unnamed > len(header_text) / 2:
        return False
    return any(is_free_text_column(df[c]) for c in df.columns if not META_COLUMN.search(str(c)))


def extract_tidy(df: pd.DataFrame, result: dict[str, Any]) -> None:
    questions = {col: clean_question_header(str(col)) for col in df.columns}
    numbered = {}
    for col, question in questions.items():
        match = re.match(r"^(\d+)\.\s", question)
        if match:
            numbered[match.group(1)] = question

    for col in df.columns:
        if META_COLUMN.search(str(col)):
            continue
        question = questions[col]
        # "Please restate your answer to Question 19" -> attach Question 19's text for context
        ref = re.search(r"answer to question (\d+)", question, re.I)
        if ref and ref.group(1) in numbered:
            question = f"{question} (Question {numbered[ref.group(1)]})"

        values = df[col]
        if is_free_text_column(values):
            for value in values.dropna():
                text = clean_text(value)
                if text and is_garbage(text) and not is_no_answer(text):
                    result["garbage_dropped"] += 1
                    continue
                if keep_response(text, use_gatekeeper=False):
                    result["responses"].append({"question": question, "text": text})
            continue

        cleaned = values.dropna().astype(str).map(clean_text)
        cleaned = cleaned[cleaned != ""]
        if cleaned.empty or cleaned.nunique() > 12:
            continue
        distribution = {str(k): int(v) for k, v in cleaned.value_counts().sort_index().items()}
        numeric = pd.to_numeric(cleaned, errors="coerce")
        mean = round(float(numeric.mean()), 2) if numeric.notna().all() else None
        result["quantitative"].append({"question": question, "n": int(len(cleaned)), "mean": mean, "distribution": distribution})


# ---------------------------------------------------------------------------
# Report-style sheets (PDF reports converted to Excel)
# ---------------------------------------------------------------------------
def _segment_stream(lines: list[tuple[tuple, int, str]]) -> list[dict[str, Any]]:
    """Group (position, column, text) lines into blocks, joining wrapped lines per column."""
    open_blocks: dict[int, dict[str, Any]] = {}
    blocks: list[dict[str, Any]] = []
    for position, column, text in lines:
        current = open_blocks.get(column)
        continues = (
            current is not None
            and not is_noise(text)
            and not is_noise(current["text"])
            and not is_question(text)
            and not RATING_SECTION.search(text)
            and not is_question(current["text"])
            and (not ends_sentence(current["text"]) or text[:1].islower())
        )
        if continues:
            current["text"] = f"{current['text']} {text}"
            continue
        if current is not None:
            blocks.append(current)
        open_blocks[column] = {"pos": position, "col": column, "text": text}
    blocks.extend(open_blocks.values())
    return sorted(blocks, key=lambda b: (b["pos"], b["col"]))


def _assign_questions(blocks: list[dict[str, Any]], result: dict[str, Any], use_gatekeeper: bool) -> None:
    current_question = None
    in_rating_section = False
    numbered_questions: dict[str, str] = {}
    for block in blocks:
        text = clean_text(block["text"])
        # A "Comments" label glued to the start of an answer: "Comments decent teacher, learned a few things."
        unlabeled = re.sub(r"^comments\s*:?\s*-?\s+", "", text, flags=re.IGNORECASE)
        if unlabeled != text and len(unlabeled.split()) >= 2:
            text = unlabeled
        rating_header = bool(RATING_SECTION.search(text)) and len(text) < 120
        if rating_header:
            # Multiple-choice section: its labels are not comments and it is not a comment question
            current_question, in_rating_section = None, True
            continue
        if is_question(text):
            current_question, in_rating_section = text.rstrip(" -"), False
            number = re.match(r"^(\d+)\.\s", current_question)
            if number:
                numbered_questions[number.group(1)] = current_question
            # "Please restate your answer to Question 19" -> attach Question 19's text for context
            ref = re.search(r"answer to question (\d+)", current_question, re.IGNORECASE)
            if ref and ref.group(1) in numbered_questions:
                current_question = f"{current_question} (Question {numbered_questions[ref.group(1)]})"
            continue
        if is_numbered_item(text):
            numbered_questions[re.match(r"^(\d+)\.\s", text).group(1)] = text
            current_question = None
            continue
        if in_rating_section and len(text.split()) < 15:
            continue  # item labels and legends inside a rating section
        if not is_noise(text) and is_garbage(text):
            result["garbage_dropped"] += 1
            continue
        if keep_response(text, use_gatekeeper):
            result["responses"].append({"question": current_question, "text": text})


def extract_report_sheet(df: pd.DataFrame, result: dict[str, Any]) -> None:
    lines: list[tuple[tuple, int, str]] = []
    scale_labels: dict[int, str] = {}
    last_label_question = None

    for row_index in range(len(df)):
        cells = [(c, clean_text(v)) for c, v in enumerate(df.iloc[row_index].tolist()) if str(v) != "nan" and clean_text(v)]
        if not cells:
            continue

        percent_cells = [(c, PERCENT_CELL.match(t)) for c, t in cells if PERCENT_CELL.match(t)]
        scale_cells = [(c, t) for c, t in cells if scale_value(t) is not None or squish(t) in SQUISHED_BLACKLIST]

        if len(scale_cells) >= 2 and len(scale_cells) >= len(cells) - 1:
            scale_labels = {c: t for c, t in scale_cells}
            continue

        if len(percent_cells) >= 2:
            label_cells = [t for c, t in cells if not PERCENT_CELL.match(t) and not re.fullmatch(r"[\d.]+", t)]
            label = label_cells[0] if label_cells else last_label_question
            if label and last_label_question and len(label) < 40 and label != last_label_question:
                label = f"{last_label_question} — {label}"
            elif label and len(label) >= 40:
                last_label_question = label
            distribution: dict[str, int] = {}
            weighted, scored = 0, 0
            for column, match in percent_cells:
                nearest = min(scale_labels, key=lambda sc: abs(sc - column)) if scale_labels else None
                name = scale_labels.get(nearest, f"column {column}") if nearest is not None and abs(nearest - column) <= 1 else f"column {column}"
                count = int(match.group(2))
                distribution[name] = distribution.get(name, 0) + count
                value = scale_value(name)
                if value is not None:
                    weighted += value * count
                    scored += count
            result["quantitative"].append({
                "question": label,
                "n": sum(distribution.values()),
                "mean": round(weighted / scored, 2) if scored else None,
                "distribution": distribution,
            })
            continue

        for column, text in cells:
            for line in strip_bullets(str(df.iat[row_index, column])).split("\n"):
                line = clean_text(line)
                if line:
                    lines.append(((row_index,), column, line))

    _assign_questions(_segment_stream(lines), result, use_gatekeeper=True)


def extract_tabular(contents: bytes, filename: str) -> dict[str, Any]:
    if filename.endswith(".csv"):
        try:
            frames = {"csv": pd.read_csv(io.BytesIO(contents), dtype=str, on_bad_lines="skip")}
        except UnicodeDecodeError:
            frames = {"csv": pd.read_csv(io.BytesIO(contents), dtype=str, on_bad_lines="skip", encoding="latin-1")}
    else:
        frames = pd.read_excel(io.BytesIO(contents), sheet_name=None, dtype=str)

    result = make_result("tabular-export")
    report_sheets = 0
    for sheet_name, df in frames.items():
        if looks_like_tidy_export(df):
            extract_tidy(df, result)
        else:
            report_sheets += 1
            raw = pd.read_csv(io.BytesIO(contents), dtype=str, header=None, on_bad_lines="skip", encoding_errors="replace") \
                if filename.endswith(".csv") else pd.read_excel(io.BytesIO(contents), sheet_name=sheet_name, dtype=str, header=None)
            extract_report_sheet(raw, result)
    if report_sheets and report_sheets == len(frames):
        result["parser"] = "report-table"
    return result


# ---------------------------------------------------------------------------
# PDF and DOCX
# ---------------------------------------------------------------------------
def extract_pdf(contents: bytes) -> dict[str, Any]:
    import pymupdf

    result = make_result("pdf")
    lines: list[tuple[tuple, int, str]] = []
    with pymupdf.open(stream=contents, filetype="pdf") as pdf:
        text_chars = 0
        for page in pdf:
            for x0, y0, _x1, _y1, block_text, block_no, block_type in page.get_text("blocks", sort=True):
                if block_type != 0:
                    continue
                text_chars += len(block_text.strip())
                # Each PDF text block is a paragraph; peel off a leading label line such as "Comments"
                block_lines = [clean_text(l) for l in strip_bullets(block_text).split("\n") if clean_text(l)]
                while len(block_lines) > 1 and (is_noise(block_lines[0]) or is_question(block_lines[0]) or squish(block_lines[0]) == "comments"):
                    lines.append(((page.number, y0, block_no, 0), 0, block_lines.pop(0)))
                if block_lines:
                    # one block = one paragraph: join its lines, columns are bucketed by x position
                    lines.append(((page.number, y0, block_no, 1), int(x0 // 60) + 1, " ".join(block_lines)))
        if text_chars < 50 * max(1, len(pdf)) // 10:
            result["warnings"].append(
                "This PDF has almost no text layer (it may be a scan). Export the evaluation as Excel/CSV, "
                "or install Tesseract OCR to read scanned pages."
            )
    result["warnings"].append("Rating tables inside PDFs are not parsed yet; only written comments were extracted.")
    _assign_questions(_merge_pdf_paragraphs(lines), result, use_gatekeeper=True)
    return result


def _merge_pdf_paragraphs(lines: list[tuple[tuple, int, str]]) -> list[dict[str, Any]]:
    """Paragraphs are already whole; only join a paragraph that continues across a page break."""
    blocks: list[dict[str, Any]] = []
    for position, column, text in lines:
        previous = blocks[-1] if blocks else None
        previous_is_question = previous is not None and is_question(previous["text"])
        # A numbered question that wraps onto the next block ("...(lectures," + "seminar discussions, ...")
        unfinished_question = (
            previous_is_question
            and re.match(r"^\d+\.\s", previous["text"])
            and not previous["text"].rstrip().endswith((":", "?", ".", ")"))
        )
        if (
            previous is not None
            and (column == previous["col"] or unfinished_question)
            and not ends_sentence(previous["text"])
            and text[:1].islower()
            and (not previous_is_question or unfinished_question)
        ):
            previous["text"] = f"{previous['text']} {text}"
            continue
        blocks.append({"pos": position, "col": column, "text": text})
    return blocks


def extract_docx(contents: bytes) -> dict[str, Any]:
    import docx

    result = make_result("docx")
    document = docx.Document(io.BytesIO(contents))
    lines = [((i,), 0, clean_text(p.text)) for i, p in enumerate(document.paragraphs) if clean_text(p.text)]
    offset = len(lines)
    for t_index, table in enumerate(document.tables):
        for r_index, row in enumerate(table.rows):
            for c_index, cell in enumerate(row.cells):
                text = clean_text(cell.text)
                if text:
                    lines.append(((offset + t_index, r_index), c_index, text))
    _assign_questions(_merge_pdf_paragraphs(lines), result, use_gatekeeper=True)
    return result


def extract(contents: bytes, filename: str) -> dict[str, Any]:
    name = filename.lower()
    if name.endswith(".pdf"):
        result = extract_pdf(contents)
    elif name.endswith(".docx"):
        result = extract_docx(contents)
    elif name.endswith((".xlsx", ".xls", ".csv")):
        result = extract_tabular(contents, name)
    else:
        raise ValueError("Unsupported file format. Use PDF, DOCX, XLSX or CSV.")

    # Drop exact repeats (the same answer printed twice in a report) while keeping order
    seen = set()
    unique = []
    for response in result["responses"]:
        key = (response["question"], response["text"])
        if key not in seen:
            seen.add(key)
            unique.append(response)
    result["responses"] = unique

    for response in result["responses"]:
        question = response["question"] or ""
        # Only trust the question when it came from a column header or a numbered survey question
        trusted = result["parser"] == "tabular-export" or bool(re.match(r"^\d+\.\s", question))
        response["non_teaching_question"] = bool(trusted and NON_TEACHING_QUESTION.search(question))

    garbage = result.pop("garbage_dropped", 0)
    if garbage >= 10 and garbage >= len(result["responses"]):
        result["warnings"].append(
            f"{garbage} text fragments were unreadable (the PDF's font has no text mapping). "
            "Export this evaluation as Excel/CSV, or re-save the PDF with readable text."
        )
    elif garbage:
        result["warnings"].append(f"{garbage} unreadable text fragments were skipped.")
    if not result["responses"]:
        result["warnings"].append("No written student comments were found in this file.")
    return result
