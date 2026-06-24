"""Verify Atmos credentials and API access (token + merchant/pay/create)."""
from types import SimpleNamespace

from django.conf import settings
from django.core.management.base import BaseCommand

from users.services import AtmosPaymentService


class Command(BaseCommand):
    help = "Check Atmos configuration and server-to-server API access."

    def handle(self, *args, **options):
        service = AtmosPaymentService()
        mode = "TEST" if settings.ATMOS_TEST_MODE else "PROD"
        self.stdout.write(f"Mode: {mode}")
        self.stdout.write(f"Base URL: {settings.ATMOS_BASE_URL}")
        self.stdout.write(f"Store ID: {settings.ATMOS_STORE_ID or '(missing)'}")
        self.stdout.write(f"Terminal ID: {settings.ATMOS_TERMINAL_ID or '(missing)'}")
        self.stdout.write(f"Callback: {settings.ATMOS_CALLBACK_URL or '(missing)'}")
        self.stdout.write(f"API key set: {bool((settings.ATMOS_API_KEY or '').strip())}")

        missing = service.missing_config_fields()
        if missing:
            self.stderr.write(self.style.ERROR(f"Missing .env: {', '.join(missing)}"))
            return

        try:
            service.get_access_token()
            self.stdout.write(self.style.SUCCESS("Token: OK"))
        except Exception as exc:
            self.stderr.write(self.style.ERROR(f"Token: FAIL — {service._format_request_error(exc)}"))
            return

        payload = service._build_merchant_pay_payload(
            SimpleNamespace(merchant_order_id="check-atmos-diag", amount=1000)
        )
        self.stdout.write(f"merchant/pay/create payload: {payload}")

        try:
            access_token, _ = service.get_access_token()
            raw = service._request_json(
                "/merchant/pay/create",
                payload=payload,
                headers=service._merchant_headers(access_token),
            )
        except Exception as exc:
            self.stderr.write(
                self.style.ERROR(f"merchant/pay/create: FAIL — {service._format_request_error(exc)}")
            )
            self.stderr.write(
                "If HTTP 403: ask Atmos to whitelist server IP and enable Merchant API "
                "for your prod Store/Terminal (partner.atmos.uz)."
            )
            return

        error = service._extract_api_error(raw)
        if error:
            self.stderr.write(self.style.ERROR(f"merchant/pay/create: {error}"))
            return

        tid = service._extract_checkout_transaction_id(raw)
        self.stdout.write(self.style.SUCCESS(f"merchant/pay/create: OK (transaction_id={tid})"))
