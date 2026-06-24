"""Print last failed Atmos payment request/response for support tickets."""

import json

from django.core.management.base import BaseCommand

from users.models import AtmosOrder


class Command(BaseCommand):
    help = "Dump request/response JSON from the latest failed Atmos order (for Atmos support)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--merchant-order-id",
            dest="merchant_order_id",
            help="Specific merchant_order_id (account) instead of the latest failure.",
        )

    def handle(self, *args, **options):
        qs = AtmosOrder.objects.filter(status=AtmosOrder.Status.FAILED).order_by("-created_at")
        if options.get("merchant_order_id"):
            qs = qs.filter(merchant_order_id=options["merchant_order_id"])
        order = qs.first()
        if not order:
            self.stderr.write(self.style.ERROR("No failed Atmos orders found."))
            return

        trace = {
            "store_id": order.response_payload.get("store_id") if order.response_payload else None,
            "merchant_order_id": order.merchant_order_id,
            "order_id": order.order_id,
            "atmos_transaction_id": order.atmos_transaction_id,
            "amount_uzs": str(order.amount),
            "amount_tiyin": int(order.amount * 100),
            "user_telegram_id": order.user.telegram_id,
            "plan": order.plan.name if order.plan else None,
            "status": order.status,
            "created_at": order.created_at.isoformat(),
            "api_flow": [
                "POST /merchant/pay/create",
                "POST /merchant/pay/pre-apply (card_token)",
                "POST /merchant/pay/apply (token OTP)",
                "POST callback -> https://api.frienfinity.uz/api/v1/payments/atmos/callback/",
            ],
            "request_to_atmos_create": order.request_payload or {},
            "response_from_atmos_last_step": order.response_payload or {},
        }

        self.stdout.write(json.dumps(trace, ensure_ascii=False, indent=2))
