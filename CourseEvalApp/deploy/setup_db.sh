#!/bin/bash
# Creates the service account, folders and the Postgres database for the Course Eval app. Safe to re-run.
set -euo pipefail
umask 022
cd /

id courseeval >/dev/null 2>&1 || useradd --system --home /opt/courseeval --shell /usr/sbin/nologin courseeval
mkdir -p /opt/courseeval /var/lib/courseeval/storage /var/backups/courseeval
chown root:courseeval /opt/courseeval            # code: owned by root, readable by the service (see install_app.sh)
chown -hR courseeval:courseeval /var/lib/courseeval   # data: the only place the service can write
chmod 750 /opt/courseeval /var/lib/courseeval

if sudo -u postgres psql -tAc "SELECT 1 FROM pg_roles WHERE rolname='courseeval'" | grep -q 1; then
  echo "database role already exists"
else
  DBPASS=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
  # The password goes to psql on standard input (printf is a shell builtin), so it never appears in a process list
  printf "CREATE ROLE courseeval LOGIN PASSWORD '%s';\n" "$DBPASS" | sudo -u postgres psql -q -v ON_ERROR_STOP=1
  sudo -u postgres psql -q -c "CREATE DATABASE courseeval OWNER courseeval;"
  # Written by the service account itself, created private from the start
  printf '%s' "$DBPASS" | sudo -u courseeval sh -c 'umask 077; cat > /var/lib/courseeval/.dbpass'
  unset DBPASS
  echo "database created"
fi
sudo -u postgres psql -tAc "SELECT datname FROM pg_database WHERE datname='courseeval'"
