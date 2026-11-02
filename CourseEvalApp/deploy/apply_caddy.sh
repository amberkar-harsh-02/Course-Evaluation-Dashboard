#!/bin/bash
# Publish the website files and switch Caddy to the new config; restore the old config if it does not validate.
set -euo pipefail
STAMP=$(date +%Y%m%d-%H%M%S)
mkdir -p /var/www/secotterlab.org/course-eval-app
rm -rf /var/www/secotterlab.org/course-eval-app/*
cp -r /tmp/course-eval-app-dist/. /var/www/secotterlab.org/course-eval-app/
chown -R root:root /var/www/secotterlab.org/course-eval-app
chmod -R a+rX /var/www/secotterlab.org/course-eval-app

cp /etc/caddy/Caddyfile /etc/caddy/Caddyfile.bak-$STAMP
cp /tmp/Caddyfile.new /etc/caddy/Caddyfile
if caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile >/tmp/caddy-validate.log 2>&1; then
  systemctl reload caddy
  echo "caddy reloaded (backup: /etc/caddy/Caddyfile.bak-$STAMP)"
else
  cp /etc/caddy/Caddyfile.bak-$STAMP /etc/caddy/Caddyfile
  echo "VALIDATION FAILED, old config restored:"; tail -5 /tmp/caddy-validate.log
  exit 1
fi
rm -rf /tmp/course-eval-app-dist /tmp/Caddyfile.new /tmp/caddy-validate.log
