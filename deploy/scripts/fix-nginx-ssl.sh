#!/usr/bin/env bash
# Fix api.frienfinity.uz serving the wrong SSL cert (e.g. vt-travel.uz default_server).
set -euo pipefail

APP_ROOT="${APP_ROOT:-/var/www/deenify}"
DOMAIN="api.frienfinity.uz"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run as root: sudo bash deploy/scripts/fix-nginx-ssl.sh"
  exit 1
fi

cd "$APP_ROOT"

echo "==> Copy nginx site + Atmos snippet"
cp deploy/nginx/deenify.conf "/etc/nginx/sites-available/deenify"
mkdir -p /etc/nginx/snippets
cp deploy/nginx/atmos-checkout-proxy.conf /etc/nginx/snippets/atmos-checkout-proxy.conf
ln -sf /etc/nginx/sites-available/deenify /etc/nginx/sites-enabled/deenify

if [[ ! -f "/etc/letsencrypt/live/${DOMAIN}/fullchain.pem" ]]; then
  echo "==> Issue Let's Encrypt certificate for ${DOMAIN}"
  certbot certonly --nginx -d "${DOMAIN}" --non-interactive --agree-tos -m admin@"${DOMAIN#api.}" || \
    certbot certonly --nginx -d "${DOMAIN}"
else
  echo "==> Certificate already exists for ${DOMAIN}"
fi

echo "==> Test and reload nginx"
nginx -t
systemctl reload nginx

echo "==> Verify certificate"
echo | openssl s_client -connect "${DOMAIN}:443" -servername "${DOMAIN}" 2>/dev/null \
  | openssl x509 -noout -subject -ext subjectAltName

echo ""
echo "Done. Bot should use BACKEND_BASE_URL=http://127.0.0.1:8001/api/v1"
echo "Then: systemctl restart deenify-bot"
