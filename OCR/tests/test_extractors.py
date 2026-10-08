"""Extractor tests built on small synthetic files (never real student data)."""
import io
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import extractors  # noqa: E402


def to_xlsx(df: pd.DataFrame, header: bool = True) -> bytes:
    buffer = io.BytesIO()
    df.to_excel(buffer, index=False, header=header)
    return buffer.getvalue()


def test_tidy_export_keeps_whole_responses_questions_and_ratings():
    df = pd.DataFrame({
        "SubjectID": ["X"] * 4,
        "Q7_5. The instructor explained concepts well._5. The instructor explained concepts well.": ["5", "4", "5", "3"],
        "Q18_10. What helped you learn? Please explain.": [
            "The worked examples were great. They made the exams feel manageable.",
            "Lectures moved too fast for me to take notes.",
            "nope",
            "Office hours helped a lot.",
        ],
        "Q41_19. Did you feel prepared, by prior coursework, for this class?": ["Prepared", "Prepared", "Unprepared", "Prepared"],
        "Q44_20. Please restate your answer to Question 19 and explain it.": [
            "I took AP chemistry in high school.", "Some chem before.", "No background at all.", "Took a prep course.",
        ],
    })
    result = extractors.extract(to_xlsx(df), "export.xlsx")

    assert result["parser"] == "tabular-export"
    texts = [r["text"] for r in result["responses"]]
    # Multi-sentence answers stay whole; "nope" is dropped
    assert "The worked examples were great. They made the exams feel manageable." in texts
    assert "nope" not in texts
    helped = next(r for r in result["responses"] if r["text"].startswith("Lectures moved"))
    assert helped["question"].startswith("10. What helped you learn?")
    assert helped["non_teaching_question"] is False
    # Question 20 is linked to Question 19, so its answers are recognised as non-teaching
    prep = next(r for r in result["responses"] if r["text"].startswith("I took AP"))
    assert "Question 19" in prep["question"] and prep["non_teaching_question"] is True

    rating = next(q for q in result["quantitative"] if q["question"].startswith("5. The instructor explained"))
    assert rating["n"] == 4 and rating["mean"] == 4.25


def test_report_sheet_joins_wrapped_lines_and_reads_percent_rows():
    rows = [
        ["CHEM 110 (01): Chemistry I", None, None, None],
        [None, "Outstanding", "Very good", "Satisfactory"],
        ["Assess your instructor's organization:", "50% (5)", "30% (3)", "20% (2)"],
        ["Please provide additional comments about your instructor: -", None, None, None],
        [None, "The professor explained every step and", None, None],
        [None, "always answered our questions.", None, None],
        [None, "Lectures were too fast at times.", None, None],
        ["Comments: -", None, None, None],
        [None, "Responses", None, None],
    ]
    result = extractors.extract(to_xlsx(pd.DataFrame(rows), header=False), "report.xlsx")

    assert result["parser"] == "report-table"
    texts = [r["text"] for r in result["responses"]]
    assert "The professor explained every step and always answered our questions." in texts
    assert "Lectures were too fast at times." in texts
    assert all(r["question"].startswith("Please provide additional comments") for r in result["responses"])

    rating = result["quantitative"][0]
    assert rating["distribution"] == {"Outstanding": 5, "Very good": 3, "Satisfactory": 2}
    assert rating["mean"] == 4.3


def test_noise_and_garbage_filters():
    assert extractors.is_noise("78.26% |")
    assert extractors.is_noise("7-9 hours 16 39.02%")
    assert extractors.is_noise("Excellent n=168 av.=.21 md= dev.=0.74")
    assert extractors.is_noise("1 - Low, 2 - Medium, 3 - High")
    assert not extractors.is_noise("Way too fast!")
    assert extractors.is_garbage("<--!-- A()# %$-*#)+*(#B- (E!#")
    assert extractors.is_garbage("=>?>@AB ==DEF GH I GJKLMNMOP")
    assert not extractors.is_garbage("The professor was clear and organized.")


def test_question_detection():
    assert extractors.is_question("16. Please describe any specific teaching practices you found helpful.")
    assert extractors.is_question("Please identify what you perceive to be the strengths and weaknesses of this instructor and course. (maximum 5000 characters)")
    assert extractors.is_question("Comments: -")
    assert not extractors.is_question("Class assignments: Homework and quizzes were too long.")
    assert not extractors.is_question("The lectures were great.")


def test_unsupported_format_raises():
    try:
        extractors.extract(b"hello", "notes.txt")
    except ValueError as exc:
        assert "Unsupported" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_bullets_are_stripped_from_answers():
    clean = extractors.clean_text
    assert clean("� Exceptional use of class time.") == "Exceptional use of class time."
    assert clean("strengths\n� good lecture pace\n� provide practice problems") == "strengths; good lecture pace; provide practice problems"
    assert clean("Strengths:\n• organized\n• clear slides") == "Strengths: organized; clear slides"
    assert clean("- Too fast\n- Too many quizzes") == "Too fast; Too many quizzes"
    assert clean("good notes • fair exams ● quick grading") == "good notes; fair exams; quick grading"
    # Inside a word the replacement character is an apostrophe, and normal dashes are kept
    assert clean("She wouldn�t repeat questions") == "She wouldn't repeat questions"
    assert clean("The exam was hard - but fair") == "The exam was hard - but fair"


def test_bulleted_cell_in_report_sheet_becomes_one_clean_answer():
    rows = [
        ["Please provide additional comments about your instructor: -", None],
        [None, "Strengths:\n� explains concepts clearly\n� answers every question"],
    ]
    result = extractors.extract(to_xlsx(pd.DataFrame(rows), header=False), "bullets.xlsx")
    assert [r["text"] for r in result["responses"]] == ["Strengths: explains concepts clearly; answers every question"]
