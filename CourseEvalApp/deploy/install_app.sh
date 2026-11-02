#!/bin/bash
# Installs/updates the Course Eval app code, Python environment, config and services. Safe to re-run.
set -euo pipefail
APP=/opt/courseeval
DATA=/var/lib/courseeval
cd /tmp

# 1. Code (OCR, NLP pipeline, backend). Existing .env files and data folders are left alone.
tar -xzf /tmp/courseeval-code.tar.gz -C "$APP"
chown -R courseeval:courseeval "$APP"

# 2. One Python environment for the backend, the NLP pipeline and the OCR server
if [ ! -x "$APP/venv/bin/python" ]; then
  sudo -u courseeval python3 -m venv "$APP/venv"
fi
sudo -u courseeval "$APP/venv/bin/pip" install -q --upgrade pip
# Server has Python 3.10, so let pip choose versions that support it (pandas 3 needs 3.11+)
sudo -u courseeval "$APP/venv/bin/pip" install -q \
  "fastapi>=0.110" "uvicorn>=0.29" "sqlalchemy>=2.0" "psycopg2-binary>=2.9" "PyJWT>=2.8" "bcrypt>=4.1" \
  "email-validator>=2.1" "python-dotenv>=1.0" "pydantic>=2.7" "cryptography>=42" "requests>=2.31" "python-multipart>=0.0.9" \
  "python-docx>=1.1" "pymupdf>=1.24" "pandas>=2.2,<3" "openpyxl>=3.1" "joblib>=1.3" "scikit-learn>=1.4" "wordninja>=2.0"

# 3. Retrain the small OCR noise classifier with this server's scikit-learn version
cd "$APP/OCR" && sudo -u courseeval "$APP/venv/bin/python" train_model.py >/dev/null && cd /tmp

# 4. Config files with fresh secrets (only created once; never overwritten)
BACKEND_ENV="$APP/CourseEvalApp/backend/.env"
if [ ! -f "$BACKEND_ENV" ]; then
  DBPASS=$(cat "$DATA/.dbpass")
  JWT=$("$APP/venv/bin/python" -c "import secrets; print(secrets.token_urlsafe(48))")
  FERNET=$("$APP/venv/bin/python" -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
  cat > "$BACKEND_ENV" <<EOF
DATABASE_URL=postgresql+psycopg2://courseeval:${DBPASS}@localhost:5432/courseeval
JWT_SECRET_KEY=${JWT}
KEY_ENCRYPTION_SECRET=${FERNET}
OCR_URL=http://127.0.0.1:8020/api/extract-text
NLP_DIR=${APP}/NLP
STORAGE_DIR=${DATA}/storage
API_HOST=127.0.0.1
API_PORT=8010
ALLOWED_ORIGINS=https://secotterlab.org
DEFAULT_YEARLY_CAP_USD=20
TOTAL_CREDIT_BUDGET_USD=0
CREDIT_YEAR_START=01-01
EOF
  echo "created backend .env"
fi
NLP_ENV="$APP/NLP/.env"
if [ ! -f "$NLP_ENV" ]; then
  cat > "$NLP_ENV" <<EOF
# Paste the lab OpenAI key after the = sign, then: sudo systemctl restart courseeval-api
OPENAI_API_KEY=
LLM_CACHE_PATH=${DATA}/llm_cache.sqlite
EOF
  echo "created NLP .env (OPENAI_API_KEY still empty)"
fi
chown courseeval:courseeval "$BACKEND_ENV" "$NLP_ENV"
chmod 600 "$BACKEND_ENV" "$NLP_ENV"

# 5. Services (only reachable from this machine; Caddy forwards to the API)
cat > /etc/systemd/system/courseeval-ocr.service <<EOF
[Unit]
Description=Course Eval - comment extraction (OCR) server
After=network.target

[Service]
User=courseeval
Group=courseeval
WorkingDirectory=${APP}/OCR
ExecStart=${APP}/venv/bin/uvicorn main:app --host 127.0.0.1 --port 8020
Restart=on-failure
NoNewPrivileges=true
ProtectSystem=full
PrivateTmp=true

[Install]
WantedBy=multi-user.target
EOF

cat > /etc/systemd/system/courseeval-api.service <<EOF
[Unit]
Description=Course Eval - merged app API (accounts, analyses, reports)
After=network.target postgresql.service courseeval-ocr.service
Wants=postgresql.service courseeval-ocr.service

[Service]
User=courseeval
Group=courseeval
WorkingDirectory=${APP}/CourseEvalApp/backend
ExecStart=${APP}/venv/bin/uvicorn app:app --host 127.0.0.1 --port 8010
Restart=on-failure
NoNewPrivileges=true
ProtectSystem=full
PrivateTmp=true
ReadWritePaths=${DATA}

[Install]
WantedBy=multi-user.target
EOF

# 6. Nightly database backup at 03:15, keep 14 days
cat > /etc/cron.d/courseeval-backup <<EOF
15 3 * * * postgres pg_dump -Fc courseeval > /var/backups/courseeval/courseeval-\$(date +\%F).dump && find /var/backups/courseeval -name '*.dump' -mtime +14 -delete
EOF
chown postgres:postgres /var/backups/courseeval
chmod 700 /var/backups/courseeval

systemctl daemon-reload
systemctl enable --now courseeval-ocr courseeval-api >/dev/null 2>&1
systemctl restart courseeval-ocr courseeval-api
sleep 4
systemctl is-active courseeval-ocr courseeval-api
curl -s http://127.0.0.1:8020/ ; echo
curl -s http://127.0.0.1:8010/api/health ; echo
