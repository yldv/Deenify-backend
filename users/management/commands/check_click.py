"""Check that Click is configured and that a checkout page can be built.

Run this after filling the CLICK_* values in .env — it never contacts Click,
it only validates the local configuration and the payment form payload.
"""

from types import SimpleNamespace

from django.conf import settings
from django.core.management.base import BaseCommand

from users.services import ClickPaymentService


class Command(BaseCommand):
    help = "Check Click configuration and the checkout form payload."

    def handle(self, *args, **options):
        service = ClickPaymentService()
        self.stdout.write(f"Payment page: {settings.CLICK_PAYMENT_URL}")
        self.stdout.write(f"Service ID:  {settings.CLICK_SERVICE_ID or '(missing)'}")
        self.stdout.write(f"Merchant ID: {settings.CLICK_MERCHANT_ID or '(missing)'}")
        self.stdout.write(
            f"Merchant user ID: {settings.CLICK_MERCHANT_USER_ID or '(not set — optional)'}"
        )
        self.stdout.write(f"Secret key set: {bool(settings.CLICK_SECRET_KEY)}")
        self.stdout.write(f"Return URL: {settings.CLICK_RETURN_URL or '(missing)'}")
        self.stdout.write(f"Callback URL: {settings.CLICK_CALLBACK_URL or '(not set in .env)'}")
        self.stdout.write(f"Bot URL: {settings.CLICK_BOT_URL}")

        missing = service.missing_config_fields()
        if missing:
            self.stderr.write(self.style.ERROR(f"Missing .env: {', '.join(missing)}"))
            return

        self.stdout.write(self.style.SUCCESS("Configuration: OK"))

        order = SimpleNamespace(
            merchant_order_id="check-click-diag",
            amount=1000,
            currency="UZS",
            plan=SimpleNamespace(name="Deenify Premium"),
        )
        fields = service.checkout_form_fields(order)
        for key, value in fields.items():
            self.stdout.write(f"  {key}: {value}")

        test_payload = {
            "click_trans_id": "12345",
            "service_id": settings.CLICK_SERVICE_ID,
            "merchant_trans_id": order.merchant_order_id,
            "merchant_prepare_id": "1",
            "amount": "1000.00",
            "action": "1",
            "sign_time": "20260101-00:00:00",
        }
        sign_string = service.build_sign_string(test_payload, settings.CLICK_SECRET_KEY)
        self.stdout.write(f"Example sign source: {sign_string[:8]}...<secret>")
        self.stdout.write(
            self.style.SUCCESS(
                "Sign check: OK — register the callback URL in my.click.uz before go-live."
            )
        )
