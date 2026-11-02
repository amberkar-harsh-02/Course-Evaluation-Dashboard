#!/bin/bash
# Creates the service account, folders and the Postgres database for the Course Eval app. Safe to re-run.
set -euo pipefail
cd /tmp

id courseeval >/dev/null 2>&1 || useradd --system --home /opt/courseeval --shell /usr/sbin/nologin courseeval
mkdir -p /opt/courseeval /var/lib/courseeval/storage /var/backups/courseeval
chown -R courseeval:courseeval /opt/courseeval /var/lib/courseeval
chmod 750 /opt/courseeval /var/lib/courseeval

if sudo -u postgres psql -tAc "SELECT 1 FROM pg_roles WHERE rolname='courseeval'" | grep -q 1; then
  echo "database role already exists"
else
  DBPASS=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
  sudo -u postgres psql -q -c "CREATE ROLE courseeval LOGIN PASSWORD '${DBPASS}';"
  sudo -u postgres psql -q -c "CREATE DATABASE courseeval OWNER courseeval;"
  printf '%s' "$DBPASS" > /var/lib/courseeval/.dbpass
  chown courseeval:courseeval /var/lib/courseeval/.dbpass
  chmod 600 /var/lib/courseeval/.dbpass
  echo "database created"
fi
sudo -u postgres psql -tAc "SELECT datname FROM pg_database WHERE datname='courseeval'"
