#!/bin/bash
# Installs/updates the Course Eval app code, Python environment, config and services. Safe to re-run.
# Run as: sudo bash ~/courseeval-deploy/install_app.sh   (inputs are read from that private folder, not /tmp)
set -euo pipefail
umask 022
APP=/opt/courseeval
DATA=/var/lib/courseeval
cd /

# 0. Inputs come from the deploying user's private folder. Refuse anything another account could have changed.
DEPLOY_DIR=${1:-$(getent passwd "${SUDO_USER:-root}" | cut -d: -f6)/courseeval-deploy}
check_private() {  # path, expected type (d or f)
  local path=$1 kind=$2 owner mode
  if [ -L "$path" ] || [ ! -$kind "$path" ]; then echo "refusing $path: missing, or not a plain $kind"; exit 1; fi
  owner=$(stat -c %u "$path"); mode=$(stat -c %a "$path")
  if [ "$owner" != 0 ] && [ "$owner" != "${SUDO_UID:-0}" ]; then echo "refusing $path: owned by another account"; exit 1; fi
  if (( 8#$mode & 8#022 )); then echo "refusing $path: writable by other accounts (mode $mode)"; exit 1; fi
}
check_private "$DEPLOY_DIR" d
CODE="$DEPLOY_DIR/courseeval-code.tar.gz"
check_private "$CODE" f

# 1. Code (OCR, NLP pipeline, backend), owned by root so the service account cannot change code that root later
#    runs. The service account can only write its data folder ($DATA). Existing .env files are left alone.
if [ ! -f "$APP/.code-owned-by-root" ]; then
  # First run after the switch: the old venv was writable by the service account, so rebuild it from scratch
  rm -rf "$APP/venv"
fi
chown -hR root:root "$APP"                      # -h: change links themselves, never what they point to
LINKS=$(find "$APP" -path "$APP/venv" -prune -o -type l -print)
if [ -n "$LINKS" ]; then
  echo "removing unexpected links from the code folder:"; echo "$LINKS"
  find "$APP" -path "$APP/venv" -prune -o -type l -delete
fi
chown root:courseeval "$APP"
chmod 750 "$APP"
tar -xzf "$CODE" -C "$APP" --no-same-owner --no-same-permissions
chmod -R go-w "$APP"

# 2. One Python environment for the backend, the NLP pipeline and the OCR server (root-owned, readable by the service)
if [ ! -x "$APP/venv/bin/python" ]; then
  python3 -m venv "$APP/venv"
fi
export PIP_ROOT_USER_ACTION=ignore  # older pip versions do not know the command-line flag
PIP=("$APP/venv/bin/pip" install -q)
"${PIP[@]}" --upgrade pip
# Server has Python 3.10, so let pip choose versions that support it (pandas 3 needs 3.11+)
"${PIP[@]}" \
  "fastapi>=0.110" "uvicorn>=0.29" "sqlalchemy>=2.0" "psycopg2-binary>=2.9" "PyJWT>=2.8" "bcrypt>=4.1" \
  "email-validator>=2.1" "python-dotenv>=1.0" "pydantic>=2.7" "cryptography>=42" "requests>=2.31" "python-multipart>=0.0.9" \
  "python-docx>=1.1" "pymupdf>=1.24" "pandas>=2.2,<3" "openpyxl>=3.1" "joblib>=1.3" "scikit-learn>=1.4" "wordninja>=2.0"

# 3. Retrain the small OCR noise classifier with this server's scikit-learn version, and precompile the code
#    (the services cannot write to the code folder, so Python cannot cache bytecode there itself)
(cd "$APP/OCR" && "$APP/venv/bin/python" train_model.py >/dev/null)
"$APP/venv/bin/python" -m compileall -q "$APP/OCR" "$APP/NLP" "$APP/CourseEvalApp/backend" >/dev/null || true
touch "$APP/.code-owned-by-root"

# 4. Config files with fresh secrets (only created once; never overwritten). Owned by root, readable by the service.
BACKEND_ENV="$APP/CourseEvalApp/backend/.env"
if [ ! -f "$BACKEND_ENV" ]; then
  DBPASS=$(sudo -u courseeval cat "$DATA/.dbpass")  # read as the service account: root never follows its files
  JWT=$("$APP/venv/bin/python" -c "import secrets; print(secrets.token_urlsafe(48))")
  FERNET=$("$APP/venv/bin/python" -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
  (umask 077; cat > "$BACKEND_ENV" <<EOF
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
  )
  echo "created backend .env"
fi
NLP_ENV="$APP/NLP/.env"
if [ ! -f "$NLP_ENV" ]; then
  (umask 077; cat > "$NLP_ENV" <<EOF
# Paste the lab OpenAI key after the = sign (sudo nano), then: sudo systemctl restart courseeval-api
OPENAI_API_KEY=
LLM_CACHE_PATH=${DATA}/llm_cache.sqlite
EOF
  )
  echo "created NLP .env (OPENAI_API_KEY still empty)"
fi
chown root:courseeval "$BACKEND_ENV" "$NLP_ENV"
chmod 640 "$BACKEND_ENV" "$NLP_ENV"

# 5. Services (only reachable from this machine; Caddy forwards to the API).
#    ProtectSystem=strict makes the whole file system read-only for the service except the paths listed.
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
ProtectSystem=strict
ProtectHome=true
PrivateTmp=true
UMask=0077

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
ProtectSystem=strict
ProtectHome=true
PrivateTmp=true
ReadWritePaths=${DATA}
UMask=0077

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
rm -f "$CODE"
