# Course Eval App (merged site)

One website where professors request an account, get approved by the admin, upload their course
evaluation files, run the AI analysis and keep their reports. It replaces the separate admin dashboard and
Professor Portal over time. Those two keep working unchanged until everyone moves over.

| Part | Folder | Port |
|---|---|---|
| Website (React) | `frontend/` | 5173 in development; served at `/course-eval-app/` in production |
| API, accounts, credits, reports | `backend/` | 8010 |
| Comment extraction (needed for analyses) | `../OCR/` | 8000 |
| AI pipeline (runs inside the backend) | `../NLP/` | none |

## Run everything locally

Use three terminals.

```powershell
# 1. OCR server
cd OCR; venv\Scripts\activate; python main.py

# 2. Backend (first time: see backend/README.md for .env and create-admin)
cd CourseEvalApp\backend; ..\..\.venv\Scripts\activate; python app.py

# 3. Website
cd CourseEvalApp\frontend; npm install; npm run dev
```

Open http://localhost:5173/course-eval-app/ and sign in with your admin account.

- **AI calls:** the backend imports the pipeline from `../NLP`. It uses the lab OpenAI key in `NLP/.env`, or a
  professor's own key.
- **Cost:** running an analysis with OpenAI costs real credit.

## What each user can do

| | Professor | Admin |
|---|---|---|
| Request an account, then sign in once approved | yes | yes |
| Upload a file and watch the analysis progress | yes | yes |
| My reports: open, review (charts, topics, ignore comments), export, delete | own reports only | own reports only |
| Account: credit left, own OpenAI key, change password | yes | yes |
| Use the local Mac Studio model | no | yes |
| Users: approve or reject, disable or enable, set credit plan and yearly $ limit | no | yes |
| Usage and credits: lab spend, budget and per-professor costs | no | yes |

Reports are private to their owner. The admin sees how many reports each professor has, but not their contents.

## Production layout (Caddy)

```
redir /course-eval-app /course-eval-app/
handle /course-eval-app/api/* {
    uri strip_prefix /course-eval-app
    reverse_proxy 127.0.0.1:8010
}
handle_path /course-eval-app/* {
    root * /var/www/<site>/course-eval-app
    try_files {path} /index.html
    file_server
}
```

Build the website with `npm run build` in `frontend/` and copy `dist/` to the folder above. The backend and
the OCR server run as services on the same machine.
