# Click automatic renewals

All finite plan periods (day/week/month/year, including multi-unit durations)
can renew. Lifetime plans never renew. Existing customers are **not** enrolled
automatically. When renewals are enabled, the bot checkout opens a card form:
customers enter their card, accept the displayed initial payment and renewal
amount/frequency, and verify Click's SMS code. The first debit is submitted in
the same flow; only a confirmed successful payment activates the saved mandate.
No separate card-binding step is needed after payment. Card checkout links
expire after 24 hours and SMS verification expires after 10 minutes.
PAN, expiry and SMS are forwarded to Click, never saved. Lifetime purchases
continue through the one-time Click checkout.

The older post-payment enrollment page remains available for legacy purchases;
its links expire 24 hours after payment. Orders paid with the integrated card
form do not show that extra enrollment link.

## Production activation

1. Confirm with Click that your service has Merchant API access and permanent
   card tokens (`temporary=0`) authorized for recurring subscription debits.
   SHOP API checkout alone does not provide reusable card tokens.
2. Install updated requirements, run `python manage.py migrate`, and collect
   the checkout CSS, JavaScript and logo with `python manage.py collectstatic --noinput`.
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
  ClickRenewalAttempt admin (initial debits are in ClickCardCheckout), or with the Django ORM
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
- SMS verification is limited to five attempts per binding. New SMS binding
  requests have no application-level cooldown. Card numbers must be 16 digits.

## Validation

`python manage.py test users.tests --settings=config.test_settings --noinput`

The isolated test settings use an in-memory database and mock Click debits.
PostgreSQL row-lock behavior and live merchant permissions still require
production/staging verification.

Current protocol reference: https://docs.click.uz/merchant-api/requests
Card-token payments require `transaction_parameter` for the local order ID.
The `merchant_trans_id` field is used by invoices and SHOP callbacks, not by
the current card-token payment request. Older SDK examples differ here.
