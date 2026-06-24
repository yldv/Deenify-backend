#!/usr/bin/env bash
# Quick check: bot -> Django on localhost (run on the server as deenify user).
set -euo pipefail

APP_ROOT="${APP_ROOT:-/var/www/deenify}"
cd "$APP_ROOT"

if [[ ! -f .env ]]; then
  echo "ERROR: $APP_ROOT/.env not found"
  exit 1
fi

set -a
# shellcheck disable=SC1091
source .env
set +a

echo "=== .env ==="
echo "BACKEND_BASE_URL=${BACKEND_BASE_URL:-<empty>}"
echo "BOT_API_SECRET length: ${#BOT_API_SECRET}"

echo ""
echo "=== services ==="
systemctl is-active deenify-web deenify-bot || true

echo ""
echo "=== localhost (no secret) ==="
curl -sS -o /tmp/deenify-diag-body.txt -w "HTTP %{http_code}\n" \
  "http://127.0.0.1:8001/api/v1/subscriptions/plans/?telegram_id=1" || true
head -c 300 /tmp/deenify-diag-body.txt; echo

echo ""
echo "=== localhost (with X-Bot-Secret) ==="
curl -sS -o /tmp/deenify-diag-body2.txt -w "HTTP %{http_code}\n" \
  -H "X-Bot-Secret: ${BOT_API_SECRET}" \
  "http://127.0.0.1:8001/api/v1/subscriptions/plans/?telegram_id=1" || true
head -c 300 /tmp/deenify-diag-body2.txt; echo

echo ""
echo "=== HTTPS certificate (api.frienfinity.uz) ==="
echo | openssl s_client -connect api.frienfinity.uz:443 -servername api.frienfinity.uz 2>/dev/null \
  | openssl x509 -noout -subject 2>/dev/null || echo "openssl failed"

echo ""
echo "=== last bot errors ==="
journalctl -u deenify-bot -n 8 --no-pager 2>/dev/null || sudo journalctl -u deenify-bot -n 8 --no-pager

echo ""
echo "Expected:"
echo "  - with secret: HTTP 200 and JSON list of plans"
echo "  - body with 'Invalid HTTP_HOST' => add 127.0.0.1 to ALLOWED_HOSTS (git pull + restart deenify-web)"
echo "  - SSL subject must be api.frienfinity.uz (not vt-travel.uz)"
