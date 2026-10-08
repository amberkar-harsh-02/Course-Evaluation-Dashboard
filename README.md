# Course Evaluation Dashboard

Turns end-of-semester course evaluations (PDF, Excel, CSV or Word exports) into a structured report that
professors can explore in a web dashboard.

For each student comment, an LLM:

1. assigns one or more of **12 instructional topics** (organization, pace, workload, engagement, clarity,
   assignments, atmosphere, communication/availability, inclusivity, assessment, grading/feedback, learning
   resources), or marks it as generic,
2. scores it **1–5 against a topic-specific rubric**,
3. summarizes the themes for each topic.

The result is one JSON report per course, with an overall score, per-topic averages, summaries and every scored
comment.

## Architecture

```
                    Admin side (run by the research team)                         Professor side
┌────────────────────┐   upload    ┌──────────────────┐  file  ┌──────────────┐
│ dashboard/         │ ──────────► │ NLP/api.py :8001 │ ─────► │ OCR/ :8000   │
│ React admin app    │ ◄────────── │ pipeline (LLM)   │ ◄───── │ text + noise │
│ :5173              │   report    └────────┬─────────┘ comments│ filtering    │
└────────────────────┘                      │ LLM calls         └──────────────┘
                                            ▼
                         Ollama (Qwen) / OpenAI / Anthropic

  report .json ──(shared with each professor)──► ProfessorPortal/frontend  (served at /course-eval/)
```

| Folder | What it is | Default port |
|---|---|---|
| `OCR/` | FastAPI server (`extractors.py`). Reads PDF/XLSX/CSV/DOCX and returns each student answer **whole**, with the survey question it answers, plus the rating tables (Excel/CSV). Survey boilerplate, rating rows and unreadable PDF text are filtered with rules and a small TF-IDF + LinearSVC classifier. | 8000 |
| `NLP/` | The LLM pipeline (`main.py`), topic and rubric definitions (`data.py`) and the API the admin dashboard calls (`api.py`). See [NLP/README.md](NLP/README.md). Research scripts are described in [NLP/experiments.md](NLP/experiments.md). | 8001 |
| `dashboard/` | Admin React app. Batch-uploads evaluation files, picks the LLM, shows run history and downloads reports as a ZIP. | 5173 |
| `ProfessorPortal/frontend/` | Professor-facing React app. Professors load their JSON report to see scores, charts, topic summaries and comments. They can ignore comments for a topic, which recalculates the scores, and export the edited JSON. | `/course-eval/` |
| `ProfessorPortal/backend/` | Optional FastAPI + PostgreSQL + JWT backend for professor accounts and stored reports. The current portal UI doesn't use it yet. | 8080 |

## Setup

Requirements: Python 3.10+, Node 18+, and either an Ollama server or an OpenAI/Anthropic API key.

```bash
git clone https://github.com/amberkar-harsh-02/Course-Evaluation-Dashboard.git
cd Course-Evaluation-Dashboard
python -m venv .venv
.venv\Scripts\activate            # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt   # installs OCR, NLP and portal-backend dependencies
```

Each service also has its own `requirements.txt` if you'd rather use separate environments.

### 1. OCR server

```bash
cd OCR
python main.py                    # http://localhost:8000
```

The classifier files (`comment_classifier.pkl`, `tfidf_vectorizer.pkl`) are included. To retrain them, run `python train_model.py`.

### 2. NLP API

```bash
cd NLP
copy .env.example .env            # add OPENAI_API_KEY / ANTHROPIC_API_KEY if needed
python api.py                     # http://127.0.0.1:8001
```

The local model is configured by `OLLAMA_URL` and `MODEL` at the top of `NLP/main.py`.

### 3. Admin dashboard

```bash
cd dashboard
npm install
npm run dev                       # http://localhost:5173
```

### 4. Professor Portal

```bash
cd ProfessorPortal/frontend
npm install
npm run dev                       # http://localhost:5173/course-eval/
```

Optional backend:

```bash
cd ProfessorPortal/backend
copy .env.example .env            # set DATABASE_URL and JWT_SECRET_KEY
python server.py                  # http://localhost:8080
python create_user.py             # create a professor account
```

## Workflow

1. Start the OCR server, then the NLP API, then the admin dashboard.
2. In the admin dashboard, choose a model, drop one or more evaluation files and start the batch. Each file becomes `NLP/saved_results/<file name>_COMBINED_REPORT.json` (plus a `.csv`).
3. Download the reports from **Batch Report** and share each one with its professor.
4. The professor opens the portal, loads the JSON and reviews it.
   - **Ignore comments:** on a topic page, a professor can mark comments to ignore. Saving recalculates the topic average and the overall score using the same rules as the pipeline.
   - **Export JSON:** downloads the edited report. Ignored comments are kept with `"ignored": true`, so they come back when the file is loaded again.

The report format is documented in [NLP/README.md](NLP/README.md#output-format).

## Deploying the Professor Portal

The portal is a static site built for the `/course-eval/` path (`vite.config.js` `base`, `BrowserRouter basename`).

```bash
cd ProfessorPortal/frontend
npm run build                     # output in dist/
```

Copy the contents of `dist/` into the folder your web server serves at `/course-eval/`. An example Caddy block:

```
redir /course-eval /course-eval/
handle_path /course-eval/* {
    root * /var/www/<site>/course-eval
    try_files {path} /index.html
    file_server
}
```

## Tests and evaluation

```bash
pip install -r requirements-dev.txt
cd OCR && pytest tests            # extractor tests (synthetic files only)
cd NLP && pytest tests            # pipeline + API tests (fake LLM, temp folders)
cd NLP && python eval.py --model openai   # accuracy against the human baselines (needs the local baseline CSVs)
```

Pipeline settings (models, parallel calls, cache, API host/CORS/key, single vs two-step mode) are documented in
`NLP/.env.example` and `NLP/settings.py`.

## Data and privacy

Course evaluations contain real student comments and instructor names. **No evaluation data is stored in this repository.**

The following are git-ignored and stay on the machine that runs the pipeline:
- uploads (`NLP/saved_inputs/`)
- generated reports (`NLP/saved_results/`)
- run history (`NLP/history.json`)
- research outputs (`NLP/results/`)
- the human-labeled baseline CSVs (`NLP/HUMAN_*.csv`)

Without the baseline CSVs, the pipeline runs without retrieved examples in its prompts, and the comparison scripts in `NLP/comparison/` can't run.

Never commit `.env` files. Use the `.env.example` templates.
