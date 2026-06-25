#!/usr/bin/env bash
# Revert auto-renewal test mode: monthly = 30 days, yearly = 365 days, daily billing timer.
set -euo pipefail

ENV_FILE="${ENV_FILE:-/var/www/deenify/.env}"

echo "==> Disabling test billing timer, enabling daily timer"
sudo systemctl disable --now deenify-billing-test.timer 2>/dev/null || true
sudo cp /var/www/deenify/deploy/systemd/deenify-billing.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now deenify-billing.timer
sudo systemctl list-timers deenify-billing.timer --no-pager || true

if [[ -f "$ENV_FILE" ]]; then
  echo "==> Removing test renewal vars from $ENV_FILE"
  sudo sed -i \
    -e '/^DEENIFY_TEST_MONTHLY_RENEWAL_MINUTES=/d' \
    -e '/^ATMOS_RENEW_LEAD_MINUTES=/d' \
    -e '/^ATMOS_RENEW_FAIL_GRACE_MINUTES=/d' \
    "$ENV_FILE"
else
  echo "WARN: $ENV_FILE not found — remove test vars manually if set."
fi

echo "==> Restarting web (reads .env for subscription duration)"
sudo systemctl restart deenify-web

echo ""
echo "Done. Production billing:"
echo "  - monthly plan period: 30 days"
echo "  - yearly plan period: 365 days"
echo "  - charge_due_subscriptions: daily (ATMOS_RENEW_LEAD_DAYS=1 by default)"
echo ""
echo "Verify: sudo -u deenify /var/www/deenify/.venv/bin/python /var/www/deenify/manage.py charge_due_subscriptions --dry-run"
echo "  (should NOT print 'TEST MODE')"
