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
- **Own keys:**
  - Professors on the "own key" plan choose an AI provider (OpenAI, Anthropic or Google Gemini) and one of
    its models on the Account page, then paste a key from that provider.
  - The model list comes from `NLP/model_catalog.py` (`GET /api/models`), and `PUT /api/me/api-model` switches
    models without re-entering the key.
  - Lab-credit plans always use the lab's GPT model.
- **Cost:** running an analysis with OpenAI costs real credit.

## What each user can do

| | Professor | Admin |
|---|---|---|
| Request an account, then sign in once approved | yes | yes |
| Upload a file and watch the analysis progress | yes | yes |
| My reports: open, review (charts, topics, ignore comments), export, delete | own reports only | own reports only |
| Compare reports across terms (score changes per topic, trend chart, Pace direction, survey ratings) | own reports only | own reports only |
| Account: credit left, own API key (provider and model), change password | yes | yes |
| Use the local Mac Studio model | no | yes |
| Users: approve or reject, disable or enable, set credit plan and yearly $ limit | no | yes |
| Usage and credits: lab spend, budget and per-professor costs | no | yes |

Reports are private to their owner. The admin sees how many reports each professor has, but not their contents.

## Design (Phase 5)

- **Type:** IBM Plex Serif for headings and scores, IBM Plex Sans for everything else. The fonts are bundled with
  the site (`@fontsource`), so the site makes no requests to outside font servers.
- **Colors:** blue-black ink on white, one accent blue for actions, and a low-to-high score scale (oxblood, slate,
  pine). A score's color always appears next to its number. Tokens are in `frontend/tailwind.config.js`.
- **Report screen** (`frontend/src/report/`): keeps the original dashboard layout.
  - The overview shows:
    - the overall grade
    - a category chart that switches between bar and radar
    - topic score cards with rings
    - a list of every analyzed comment, with search, topic and score filters and sorting
  - Clicking a card or bar opens a pop-up with the topic's numbers, a score-spread chart, its Pace direction, the AI
    summary and its comments.
  - "View more details" opens the full topic page (`?topic=Pace`), where "Ignore comments" removes comments from
    the score and recalculates it.
  - Topics with fewer than 5 scored comments are faded and labelled "few".
  - Comment lists are split into pages, 20 per page by default (10, 20 or 50), with First, Previous, page
    numbers, Next and Last. Ticks in ignore mode are kept across pages.
  - Light and dark mode: the toggle sits in the sidebar footer and is remembered per browser.
- **Sidebar:** when a report is open, its course appears under My reports with the topics nested below it and each
  topic's score. Selecting one opens that topic's page (`?topic=`).
- **Guide** (`/guide`, `pages/Guide.jsx`):
  - It opens on its own the first time a professor signs in. `users.guide_seen_at` is null until then, and
    `POST /api/auth/guide-seen` sets it.
  - It is always reachable from the sidebar.
  - It covers what the site does, step-by-step use with screenshots, the analysis description link and the feedback
    survey link.
  - The screenshots in `src/assets/guide/` show made-up demo data only.
- **New analysis:**
  - The drop zone checks the file type and size before upload.
  - After a file is chosen, it shows a file card with Replace and Remove.
  - While an analysis runs, a three-step progress list replaces the single bar.
- **Motion:** short CSS animations:
  - pages fade in
  - the pop-up scales in
  - rings, bars and score spreads fill
  - the sidebar tree slides open

  When the device asks for reduced motion, all animation is switched off.
- **Score logic:** `report/model.js` holds the score recalculation used by ignore mode. It mirrors `NLP/main.py`
  and matches the pipeline exactly on all saved reports.
- **Phones:** the sidebar becomes a top bar with a menu.

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
