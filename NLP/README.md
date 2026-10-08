# NLP Pipeline

This folder holds the LLM pipeline that turns course-evaluation comments into topic scores and summaries, plus the
FastAPI bridge (`api.py`) that the admin dashboard calls. It also contains the research scripts that compared
Llama3, Gemma, roBERTa and DistilroBERTa (see [experiments.md](experiments.md)).

## Files

| File | Purpose |
|---|---|
| `main.py` | `analysis_pipeline()`: classify, score, summarize, write report |
| `data.py` | Topic definitions (`TOPIC_DEFS`, `TOPIC_KEYS`), the 1–5 `SCORING_RUBRIC`, and sample comments used by experiments |
| `api.py` | FastAPI server on port 8001: upload file, call OCR server, run pipeline, keep history, export ZIP |
| `experiments/`, `comparison/` | Research scripts for model comparison (not used by the app) |

## Running the API

```bash
python -m venv .venv
.venv\Scripts\activate          # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
copy .env.example .env          # then fill in API keys if you use OpenAI or Anthropic
python api.py                   # http://localhost:8001
```

The OCR server (`../OCR`) must be running on port 8000, because `api.py` sends every upload there first.

### Endpoints

| Method | Path | What it does |
|---|---|---|
| POST | `/api/analyze` | Form fields `file` and `model_choice` (`local`, `openai`, `anthropic`). Saves the upload to `saved_inputs/`, extracts comments with the OCR server, runs the pipeline, and writes `saved_results/<course_id>_COMBINED_REPORT.json` and `.csv`. |
| GET | `/api/history` | Run history from `history.json` |
| DELETE | `/api/history` | Clears the history |
| POST | `/api/download-zip` | Body `{"course_ids": [...]}`. Returns a ZIP of the matching JSON reports. |
| GET | `/api/download/{course_id}` | Returns one JSON report |

`course_id` is the uploaded file name without its extension.

## Model choices

`call_llm()` in `main.py` sends raw HTTP requests:

- `local` (default): Ollama `/api/generate` at `OLLAMA_URL` with model `MODEL` (currently `qwen35b:latest` on the lab Mac Studio).
- `openai`: Chat Completions. Needs `OPENAI_API_KEY` in `.env`.
- `anthropic`: Messages API. Needs `ANTHROPIC_API_KEY` in `.env`.

## Pipeline steps

For each comment, in order:

1. Exact duplicates are removed.
2. **Classification** (`classify_with_llama`): the LLM returns every matching topic out of the 12 in `data.py`, or `None of the above / Other`. Regex hints in `add_high_precision_topic_hints` can add extra topics.
3. **Scoring** (`sentiment_with_llama`): each (comment, topic) pair gets a 1–5 rubric score, a confidence and an evidence quote. Sentiment is derived from the score: 1–2 negative, 3 neutral, 4–5 positive.
4. **Filtering**: a pair is dropped when the model says the topic isn't supported or when the confidence is below the topic's value in `CONFIDENCE_THRESHOLDS`. A comment with no topic left goes to `None of the above / Other`.

After all comments are processed:

5. **Aggregation**:
   - A topic's average is the mean of its scores.
   - The overall score is the mean, over comments, of each comment's average topic score.
   - `reliability` flags topics with fewer than 5 scored comments, low confidence or model errors.
6. **Summaries** (`summarize_topic_with_llama`): one LLM call per topic.

### Optional examples for the prompts (RAG)

If `HUMAN_CATEGORIZED_OUTPUT.csv` and `HUMAN_SENTIMENT_BASELINE.csv` exist in this folder, the most similar
human-labeled rows are added to each prompt as calibration examples. These files contain real student comments,
so they are **not in the repository**. Without them the pipeline still runs, but it can be less accurate.

## Output format

```json
{
  "course_id": "CHEM_14A_Fall2025",
  "model": "local",
  "overall_score": 4.12,
  "category_scores": [{"category": "Pace", "average_score": 3.5, "comment_count": 6}],
  "topic_summaries": [{"topic": "Pace", "summary": "Summary of Pace: ..."}],
  "categories": [{
    "topic": "Pace", "average_score": 3.5, "comment_count": 6,
    "scored_comment_count": 6, "reliability": "reliable",
    "comments": [{"feedback": "...", "classification_status": "classified", "topic_supported": true,
                  "evidence_quote": "...", "sentiment": "positive", "score": 4, "confidence": 0.8,
                  "scoring_status": "scored", "reasoning": "..."}]
  }],
  "metadata": {"input_comments": 40, "processed_comments": 38, "duplicates_removed": 2,
               "scored_comments": 30, "generic_comments": 8, "warnings": [], "runtime_seconds": 600.5}
}
```

`null` values inside comments are written as `""`. The Professor Portal may add `"ignored": true` to a comment
when a professor excludes it from a topic's score.

## Using the pipeline from Python

```python
from main import analysis_pipeline

output = analysis_pipeline(
    course_id="MY_COURSE",
    raw_comments=["The lectures were clear and organized.", "The exams felt rushed."],
    write_files=False,       # True writes JSON + CSV into output_dir (default results/combined/)
    model_choice="local",
)
```

Other options: `output_dir`, `dedupe_exact_comments`, `use_rag`.

## Contribution notes

- Keep topic names in `data.py`. If you add, remove or rename a topic, update `TOPIC_DEFS`, `SCORING_RUBRIC` and the baseline CSV columns.
- Keep the output format stable. The admin dashboard and the Professor Portal both read it.
- Never commit raw course evaluations or generated reports. `saved_inputs/`, `saved_results/` and `results/` are git-ignored.
- Quick check before handing off a change: `python -m py_compile main.py data.py api.py`
