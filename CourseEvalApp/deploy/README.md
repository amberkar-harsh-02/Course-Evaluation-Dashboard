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
  `install_app.sh`, owned by root and readable by the `courseeval` service account (mode 640), and are never overwritten.
- **Ownership:** the code folder `/opt/courseeval` (including the venv) is owned by root. The services run as
  `courseeval` with `ProtectSystem=strict`, so they can only write `/var/lib/courseeval` and their private `/tmp`.
  A compromised service therefore cannot change code that root runs on the next deploy.

## Scripts (run from your laptop; each is safe to re-run)

Deploy inputs go to a private folder in the deploying account's home, `~/courseeval-deploy` (mode 700), never to
the shared `/tmp`. The scripts refuse inputs that are links, owned by another account, or writable by others.

| Script | What it does |
|---|---|
| `setup_db.sh` | First time only: service account, folders, Postgres role and database (the password is passed on standard input, never on a command line) |
| `install_app.sh` | Installs or updates code (from `~/courseeval-deploy/courseeval-code.tar.gz`), Python packages, config, services and the backup job, then restarts the services. The first run after this change rebuilds the venv as root, which takes a few minutes. |
| `apply_caddy.sh` | Publishes the website (from `~/courseeval-deploy/course-eval-app-dist`) and installs `~/courseeval-deploy/Caddyfile.new`. If the new Caddy config doesn't validate, it restores the old one. |

## Update the live site after code changes

Run these in Git Bash from `Main/`:

```bash
KEY=~/.ssh/quiz-app-deploy; H=ubuntu@15.204.118.48; D=courseeval-deploy
ssh -i $KEY $H "mkdir -p -m 700 ~/$D && chmod 700 ~/$D"

# Backend + pipeline + OCR code
TMP=$(mktemp -d)
tar -czf $TMP/courseeval-code.tar.gz OCR/main.py OCR/extractors.py OCR/train_model.py OCR/requirements.txt   NLP/main.py NLP/data.py NLP/settings.py NLP/llm_cache.py NLP/llm_context.py NLP/model_catalog.py NLP/requirements.txt   NLP/HUMAN_CATEGORIZED_OUTPUT.csv NLP/HUMAN_SENTIMENT_BASELINE.csv   CourseEvalApp/backend/*.py CourseEvalApp/backend/requirements.txt
scp -i $KEY $TMP/courseeval-code.tar.gz CourseEvalApp/deploy/install_app.sh $H:$D/
ssh -i $KEY $H "sudo bash ~/$D/install_app.sh"
rm -rf $TMP

# Website
(cd CourseEvalApp/frontend && npm run build)
ssh -i $KEY $H "rm -rf ~/$D/course-eval-app-dist && mkdir -m 755 ~/$D/course-eval-app-dist && sudo cat /etc/caddy/Caddyfile > ~/$D/Caddyfile.new"
scp -i $KEY -r CourseEvalApp/frontend/dist/. $H:$D/course-eval-app-dist/
scp -i $KEY CourseEvalApp/deploy/apply_caddy.sh $H:$D/
ssh -i $KEY $H "sudo bash ~/$D/apply_caddy.sh"
```

## Useful commands on the server

```bash
sudo systemctl status courseeval-api courseeval-ocr
sudo journalctl -u courseeval-api -n 100          # logs
sudo systemctl restart courseeval-api             # after editing a .env file
ls /var/backups/courseeval                        # nightly database dumps
```
