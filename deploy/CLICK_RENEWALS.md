# Click automatic renewals

All finite plan periods (day/week/month/year, including multi-unit durations)
can renew. Lifetime plans never renew. Existing customers are **not** enrolled
automatically. After paying, customers open the enrollment link on the return
page or in the bot's success message, accept the displayed amount/frequency,
and verify their card with Click's SMS code. Enrollment links expire 24 hours
after payment. PAN, expiry and SMS are forwarded to Click, never saved.

## Production activation

1. Confirm with Click that your service has Merchant API access and permanent
   card tokens (`temporary=0`) authorized for recurring subscription debits.
   SHOP API checkout alone does not provide reusable card tokens.
2. Install updated requirements and run `python manage.py migrate`.
3. Generate a dedicated key with
   `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`.
   Save it as `CLICK_TOKEN_ENCRYPTION_KEY` in the server's environment. Back up
   this key securely: rotating/removing it makes existing tokens unreadable.
4. Configure `CLICK_SERVICE_ID`, `CLICK_SECRET_KEY`, `CLICK_MERCHANT_USER_ID`,
   and the HTTPS `BACKEND_PUBLIC_URL`. Set `CLICK_RENEWALS_ENABLED=True` only
   after the merchant permissions are confirmed. Restart the web service.
5. Install `deenify-renewals.service` and `deenify-renewals.timer` from
   `deploy/systemd/` into `/etc/systemd/system/`, then run
   `sudo systemctl daemon-reload` and
   `sudo systemctl enable --now deenify-renewals.timer`.
6. Verify enrollment and one renewal with an authorized test customer before
   enabling the timer for production customers. No real card was charged in
   the automated tests.

## Behavior and operations

- Each debit has a durable order and a unique (mandate, due date) attempt.
  Duplicate scheduler runs do not repeat a debit. Disable the feature globally
  with `CLICK_RENEWALS_ENABLED=False` and restart both web/timer services.
- Due time follows the subscription's actual expiry, including referral days.
  A plan/price/currency change disables the mandate and requires new consent.
- A declined debit disables renewal and sends a bot notice. The customer can
  purchase again and re-enroll. There are no automatic decline retries.
- A network timeout/crash leaves a `processing` or `uncertain` attempt. It is
  **never resubmitted automatically**. Monitor these rows in the read-only
  ClickRenewalAttempt admin (or with the Django ORM)
  and reconcile the merchant order ID in the Click cabinet/support. A valid
  successful SHOP callback can confirm the order normally. Do not delete an
  uncertain attempt or create a replacement debit before confirming its outcome.
- Bot cancellation stops future debits and erases the local encrypted token;
  paid coverage stays active until expiry. A debit already submitted to Click
  may still finish. This does not issue a refund or delete the token at Click.
- Unpaid-order cleanup excludes renewal attempts, preserving reconciliation
  records. Keep normal database backups. Card-token fields must never be added
  to admin display/API responses/logging. Configure request-body logging at
  proxies/error reporting to exclude the enrollment endpoint.
- SMS verification is limited to five attempts per binding; requesting a new
  binding has a 60-second cooldown.

## Validation

`python manage.py test users.tests --settings=config.test_settings --noinput`

The isolated test settings use an in-memory database and mock Click debits.
PostgreSQL row-lock behavior and live merchant permissions still require
production/staging verification.

Protocol reference: https://github.com/click-llc/click-integration-php
(`click/models/Payments.php` and `BasePayments.php`).
