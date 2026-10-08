# NLP Pipeline

This folder holds the LLM pipeline that turns course-evaluation comments into topic scores and summaries, plus the
FastAPI bridge (`api.py`) that the admin dashboard calls. It also contains the research scripts that compared
Llama3, Gemma, roBERTa and DistilroBERTa (see [experiments.md](experiments.md)).

## Files

| File | Purpose |
|---|---|
| `main.py` | `analysis_pipeline()`: analyze each comment, aggregate scores, summarize topics, write the report |
| `data.py` | Topic definitions (`TOPIC_DEFS`, `TOPIC_KEYS`), the 1–5 `SCORING_RUBRIC`, and sample comments used by experiments |
| `settings.py` | Every runtime setting (models, URLs, parallelism, cache, API host/CORS/key). Each can be overridden in `.env` |
| `llm_cache.py` | SQLite cache of LLM answers (`cache/llm_cache.sqlite`) so re-runs with unchanged prompts are free |
| `api.py` | FastAPI server on port 8001: upload file, call OCR server, run pipeline, keep history, export ZIP |
| `eval.py` | Scores the pipeline against the human-labeled baselines (topic F1, score MAE) |
| `tests/` | pytest suite. A fake LLM is used, so tests cost nothing and never touch real data |
| `experiments/`, `comparison/` | Research scripts for model comparison (not used by the app) |

## Running the API

```bash
python -m venv .venv
.venv\Scripts\activate          # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
copy .env.example .env          # then fill in API keys if you use OpenAI or Anthropic
python api.py                   # http://127.0.0.1:8001
```

The OCR server (`../OCR`) must be running on port 8000, because `api.py` sends every upload there first.

By default the API listens on `127.0.0.1` only and accepts browser requests from the dashboard
(`localhost:5173`). Set `API_HOST=0.0.0.0` and `ALLOWED_ORIGINS` in `.env` if other machines need access, and
set `NLP_API_KEY` so those requests must carry an `X-API-Key` header.

### Endpoints

| Method | Path | What it does |
|---|---|---|
| POST | `/api/analyze` | Form fields `file` and `model_choice` (`local`, `openai`, `anthropic`). Processes the file and returns the finished report. Used by the admin dashboard. |
| POST | `/api/jobs` | Same form fields, but returns a `job_id` right away and processes the file in the background. |
| GET | `/api/jobs/{job_id}` | Job status (`queued`, `running`, `complete`, `failed`) with `stage` and `done`/`total` progress. |
| GET | `/api/jobs` | All jobs since the server started. |
| GET | `/api/history` | Run history from `history.json` |
| DELETE | `/api/history` | Clears the history |
| POST | `/api/download-zip` | Body `{"course_ids": [...]}`. Returns a ZIP of the matching JSON reports. |
| GET | `/api/download/{course_id}` | Returns one JSON report |

`course_id` is the uploaded file name without its extension. Uploading the same file again moves the old report to
`saved_results/archive/` instead of overwriting it.

## Model choices

`call_llm()` in `main.py` sends raw HTTP requests:

- `local` (default): Ollama `/api/generate` at `OLLAMA_URL` with model `OLLAMA_MODEL` (currently `qwen35b:latest` on the lab Mac Studio).
- `openai`: Chat Completions with structured outputs. Needs `OPENAI_API_KEY` in `.env`.
- `anthropic`: Messages API with a forced tool call. Needs `ANTHROPIC_API_KEY` in `.env`.

Model IDs live in `settings.py` and are written into every report (`metadata.model_id`).

## Pipeline steps

1. **Input:** whole student responses, each with the survey question it answers (from the OCR server). Plain strings
   also work. Exact duplicates are removed.
2. **Non-teaching questions:** answers to questions such as "Did you feel prepared by prior coursework?" are put in
   Other without any LLM call (`metadata.non_teaching_skipped`).
3. **Analysis** (`analyze_comment`, `PIPELINE_MODE=single`): one LLM call per comment, with a JSON schema the provider
   enforces. It returns every topic the comment talks about, a 1–5 rubric score per topic, confidence, an evidence
   quote, and for Pace the direction (`too_fast`, `too_slow`, `appropriate`). Generic comments ("Great professor!")
   get a `general_sentiment_score` instead. The survey question is included in the prompt as context.
   `PIPELINE_MODE=two_step` switches back to the older flow (one classification call plus one scoring call per topic).
4. **Filtering:** a topic score is dropped when its confidence is below the topic's value in
   `CONFIDENCE_THRESHOLDS` (`CONFIDENCE_GATE=off` disables this). Every drop is counted in
   `metadata.dropped_topic_assignments`, and model errors in `metadata.classification_errors` / `scoring_errors`.
5. **Aggregation:**
   - A topic's average is the mean of its scores.
   - The overall score is the mean, over comments, of each comment's average topic score.
   - `general_sentiment` (generic comments) is reported separately and never changes the overall score.
   - `reliability` flags topics with fewer than 5 scored comments, low confidence or model errors.
6. **Summaries** (`summarize_topic`): one LLM call per topic.

LLM calls run in parallel (`MAX_PARALLEL_API_CALLS`, default 8, or `MAX_PARALLEL_LOCAL_CALLS`, default 2), and
answers are cached, so re-running a file with unchanged prompts and model makes no new calls.

### Optional examples for the prompts (RAG)

If `HUMAN_CATEGORIZED_OUTPUT.csv` and `HUMAN_SENTIMENT_BASELINE.csv` exist in this folder, the most similar
human-labeled rows are added to each prompt as calibration examples. These files contain real student comments,
so they are **not in the repository**. Without them the pipeline still runs, but it can be less accurate.

## Output format

```json
{
  "course_id": "CHEM_14A_Fall2025",
  "model": "openai",
  "overall_score": 4.12,
  "category_scores": [{"category": "Pace", "average_score": 3.5, "comment_count": 6}],
  "topic_summaries": [{"topic": "Pace", "summary": "Summary of Pace: ..."}],
  "categories": [{
    "topic": "Pace", "average_score": 3.5, "comment_count": 6,
    "scored_comment_count": 6, "reliability": "reliable",
    "direction_counts": {"too_fast": 5, "too_slow": 0, "appropriate": 1},
    "comments": [{"feedback": "...", "question": "What could be improved?", "classification_status": "classified",
                  "topic_supported": true, "evidence_quote": "...", "sentiment": "negative", "score": 2,
                  "confidence": 0.8, "scoring_status": "scored", "reasoning": "...", "direction": "too_fast",
                  "general_score": ""}]
  }],
  "quantitative": [{"question": "Assess your instructor's organization", "n": 87, "mean": 4.66,
                    "distribution": {"Outstanding": 60, "Very good": 24, "Satisfactory": 3}}],
  "general_sentiment": {"average_score": 4.8, "scored_comments": 12, "positive": 12, "neutral": 0, "negative": 0},
  "metadata": {"input_comments": 40, "processed_comments": 38, "duplicates_removed": 2, "non_teaching_skipped": 5,
               "parser": "tabular-export", "extraction_warnings": [], "scored_comments": 30, "generic_comments": 8,
               "model_id": "gpt-5.6-terra", "prompt_version": "2026-10-08.3", "pipeline_mode": "single",
               "confidence_gate": true, "classification_errors": 0, "scoring_errors": 0,
               "dropped_topic_assignments": {"topic_unsupported": 0, "low_confidence": 3, "all_topics_rejected": 1},
               "warnings": [], "runtime_seconds": 60.5}
}
```

- `null` values inside comments are written as `""`.
- `direction_counts` only appears on the Pace category.
- `quantitative` holds the rating tables found in the file (Excel/CSV exports; PDF rating tables are not parsed yet).
- The Professor Portal may add `"ignored": true` to a comment when a professor excludes it from a topic's score.
- Reports made before 2026-10-08 lack the newer fields. Their Pace scores used the old rubric
  (1 = too fast, 2 = too slow, …), so Pace averages of old and new reports are not comparable.

## Using the pipeline from Python

```python
from main import analysis_pipeline

output = analysis_pipeline(
    course_id="MY_COURSE",
    raw_comments=[
        {"text": "The lectures were clear and organized.", "question": "What helped you learn?"},
        "The exams felt rushed.",
    ],
    write_files=False,       # True writes JSON + CSV into output_dir (default results/combined/)
    model_choice="openai",
    progress=lambda stage, done, total: print(stage, done, total),
)
```

Other options: `output_dir`, `dedupe_exact_comments`, `use_rag`, `quantitative`, `extraction`.

## Measuring changes

```bash
python eval.py --model openai            # full run on the human baselines
python eval.py --model openai --limit 20 # quick check
```

It prints topic micro/macro F1 and score MAE, coverage and ±1 accuracy, and saves details to `eval_runs/` (git-ignored).
Run it before and after any prompt or scoring change, and bump `PROMPT_VERSION` in `settings.py`.

## Tests

```bash
pip install pytest httpx
pytest tests
```

## Contribution notes

- Keep topic names in `data.py`. If you add, remove or rename a topic, update `TOPIC_DEFS`, `SCORING_RUBRIC` and the baseline CSV columns.
- Keep the output format stable: only add fields. The admin dashboard and the Professor Portal both read it.
- Never commit raw course evaluations or generated reports. `saved_inputs/`, `saved_results/`, `results/`, `eval_runs/` and `cache/` are git-ignored.
