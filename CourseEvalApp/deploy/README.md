# Deploying the Course Eval app to the Caddy server

The server (`ubuntu@15.204.118.48`, Ubuntu 22.04) runs:
- **Postgres:** database `courseeval`, reachable only from the server itself.
- **`courseeval-ocr`:** comment extraction on 127.0.0.1:8020.
- **`courseeval-api`:** the app API on 127.0.0.1:8010. It runs the NLP pipeline in-process.
- **Caddy:** serves the website from `/var/www/secotterlab.org/course-eval-app` and forwards `/course-eval-app/api/*` to the API.

Layout on the server:
- **Code:** `/opt/courseeval/{OCR,NLP,CourseEvalApp/backend}`, with one venv at `/opt/courseeval/venv`.
- **Data:**
  - uploads: `/var/lib/courseeval/storage`
  - LLM cache: `/var/lib/courseeval/llm_cache.sqlite`
  - nightly database dumps: `/var/backups/courseeval` (kept 14 days)
- **Secrets:** `/opt/courseeval/CourseEvalApp/backend/.env` and `/opt/courseeval/NLP/.env`. They are created once by
  `install_app.sh`, are readable only by the `courseeval` service account, and are never overwritten.

## Scripts (run from your laptop; each is safe to re-run)

| Script | What it does |
|---|---|
| `setup_db.sh` | First time only: service account, folders, Postgres role and database |
| `install_app.sh` | Installs or updates code (from `/tmp/courseeval-code.tar.gz`), Python packages, config, services and the backup job, then restarts the services |
| `apply_caddy.sh` | Publishes the website (from `/tmp/course-eval-app-dist`) and installs `/tmp/Caddyfile.new`. If the new Caddy config doesn't validate, it restores the old one. |

## Update the live site after code changes

Run these in Git Bash from `Main/`:

```bash
KEY=~/.ssh/quiz-app-deploy; H=ubuntu@15.204.118.48
# Backend + pipeline + OCR code
tar -czf /tmp/courseeval-code.tar.gz OCR/main.py OCR/extractors.py OCR/train_model.py OCR/requirements.txt \
  NLP/main.py NLP/data.py NLP/settings.py NLP/llm_cache.py NLP/llm_context.py NLP/requirements.txt \
  NLP/HUMAN_CATEGORIZED_OUTPUT.csv NLP/HUMAN_SENTIMENT_BASELINE.csv \
  CourseEvalApp/backend/*.py CourseEvalApp/backend/requirements.txt
scp -i $KEY /tmp/courseeval-code.tar.gz CourseEvalApp/deploy/install_app.sh $H:/tmp/
ssh -i $KEY $H 'sudo bash /tmp/install_app.sh'

# Website
(cd CourseEvalApp/frontend && npm run build)
ssh -i $KEY $H 'rm -rf /tmp/course-eval-app-dist && mkdir /tmp/course-eval-app-dist && sudo cp /etc/caddy/Caddyfile /tmp/Caddyfile.new'
scp -i $KEY -r CourseEvalApp/frontend/dist/. $H:/tmp/course-eval-app-dist/
scp -i $KEY CourseEvalApp/deploy/apply_caddy.sh $H:/tmp/
ssh -i $KEY $H 'sudo bash /tmp/apply_caddy.sh'
```

## Useful commands on the server

```bash
sudo systemctl status courseeval-api courseeval-ocr
sudo journalctl -u courseeval-api -n 100          # logs
sudo systemctl restart courseeval-api             # after editing a .env file
ls /var/backups/courseeval                        # nightly database dumps
```
