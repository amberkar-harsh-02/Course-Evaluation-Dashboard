#!/bin/bash
# Publish the website files and switch Caddy to the new config; restore the old config if it does not validate.
# Run as: sudo bash ~/courseeval-deploy/apply_caddy.sh   (inputs are read from that private folder, not /tmp)
set -euo pipefail
umask 022
cd /

DEPLOY_DIR=${1:-$(getent passwd "${SUDO_USER:-root}" | cut -d: -f6)/courseeval-deploy}
check_private() {  # path, expected type (d or f)
  local path=$1 kind=$2 owner mode
  if [ -L "$path" ] || [ ! -$kind "$path" ]; then echo "refusing $path: missing, or not a plain $kind"; exit 1; fi
  owner=$(stat -c %u "$path"); mode=$(stat -c %a "$path")
  if [ "$owner" != 0 ] && [ "$owner" != "${SUDO_UID:-0}" ]; then echo "refusing $path: owned by another account"; exit 1; fi
  if (( 8#$mode & 8#022 )); then echo "refusing $path: writable by other accounts (mode $mode)"; exit 1; fi
}
check_private "$DEPLOY_DIR" d
DIST="$DEPLOY_DIR/course-eval-app-dist"
NEW_CADDYFILE="$DEPLOY_DIR/Caddyfile.new"
check_private "$DIST" d
check_private "$NEW_CADDYFILE" f
if [ -n "$(find "$DIST" -type l)" ]; then echo "refusing $DIST: it contains links"; exit 1; fi

SITE=/var/www/secotterlab.org/course-eval-app
STAMP=$(date +%Y%m%d-%H%M%S)
mkdir -p "$SITE"
rm -rf "${SITE:?}"/*
cp -r "$DIST"/. "$SITE"/
chown -R root:root "$SITE"
chmod -R a+rX,go-w "$SITE"

LOG=$(mktemp)
trap 'rm -f "$LOG"' EXIT
cp /etc/caddy/Caddyfile /etc/caddy/Caddyfile.bak-$STAMP
install -m 644 -o root -g root "$NEW_CADDYFILE" /etc/caddy/Caddyfile
if caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile >"$LOG" 2>&1; then
  systemctl reload caddy
  echo "caddy reloaded (backup: /etc/caddy/Caddyfile.bak-$STAMP)"
else
  cp /etc/caddy/Caddyfile.bak-$STAMP /etc/caddy/Caddyfile
  echo "VALIDATION FAILED, old config restored:"; tail -5 "$LOG"
  exit 1
fi
rm -rf "$DIST" "$NEW_CADDYFILE"
