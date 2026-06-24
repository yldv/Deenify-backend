"""Print failed Atmos payment request/response per API step (for Atmos support)."""

import json

from django.conf import settings
from django.core.management.base import BaseCommand

from users.models import AtmosOrder


def _legacy_steps(order):
    """Reconstruct steps when atmos_trace was not stored (older orders)."""
    create_request = order.request_payload or {}
    last_response = {}
    if isinstance(order.response_payload, dict):
        if order.response_payload.get("last_error_response"):
            last_response = order.response_payload["last_error_response"]
        elif order.response_payload.get("result"):
            last_response = order.response_payload
        else:
            last_response = order.response_payload

    store_id = create_request.get("store_id") or settings.ATMOS_STORE_ID
    txn_id = order.atmos_transaction_id

    steps = [
        {
            "step": "1. POST /merchant/pay/create",
            "request": create_request,
            "response": {
                "note": "create response was overwritten in DB; transaction_id taken from order",
                "transaction_id": txn_id,
            }
            if last_response.get("result")
            else last_response,
        },
        {
            "step": "2. POST /merchant/pay/pre-apply",
            "request": {
                "store_id": store_id,
                "transaction_id": int(txn_id) if str(txn_id).isdigit() else txn_id,
                "card_token": "<bound card token — masked>",
            },
            "response": {
                "note": "not stored; assumed OK because failure happened on apply"
            },
        },
        {
            "step": "3. POST /merchant/pay/apply",
            "request": {
                "store_id": store_id,
                "transaction_id": int(txn_id) if str(txn_id).isdigit() else txn_id,
                "otp": "<ATMOS_TOKEN_PAYMENT_OTP — masked>",
            },
            "response": last_response,
        },
        {
            "step": "4. POST callback -> merchant",
            "request": {
                "note": "Atmos calls "
                + (settings.ATMOS_CALLBACK_URL or "ATMOS_CALLBACK_URL")
                + " during apply; payload was not stored"
            },
            "response": {"note": "merchant should return status=1; check nginx/access logs"},
        },
    ]
    return steps


def _trace_steps(order):
    payload = order.response_payload if isinstance(order.response_payload, dict) else {}
    trace = payload.get("atmos_trace") or []
    if trace:
        return [
            {
                "step": f"{index}. {entry.get('step', 'unknown')}",
                "request": entry.get("request") or {},
                "response": entry.get("response") or {},
            }
            for index, entry in enumerate(trace, start=1)
        ]
    return _legacy_steps(order)


class Command(BaseCommand):
    help = "Dump per-step Atmos request/response from the latest failed order (for Atmos support)."

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
        order = qs.select_related("user", "plan").first()
        if not order:
            self.stderr.write(self.style.ERROR("No failed Atmos orders found."))
            return

        payload = order.response_payload if isinstance(order.response_payload, dict) else {}
        trace = {
            "merchant_order_id": order.merchant_order_id,
            "order_id": order.order_id,
            "atmos_transaction_id": order.atmos_transaction_id,
            "amount_uzs": str(order.amount),
            "amount_tiyin": int(order.amount * 100),
            "user_telegram_id": order.user.telegram_id,
            "plan": order.plan.name if order.plan else None,
            "status": order.status,
            "created_at": order.created_at.isoformat(),
            "failed_step": payload.get("last_step"),
            "error_code": (payload.get("result") or {}).get("code")
            or (payload.get("last_error_response") or {}).get("result", {}).get("code"),
            "steps": _trace_steps(order),
        }

        self.stdout.write(json.dumps(trace, ensure_ascii=False, indent=2))
