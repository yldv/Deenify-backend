import json
from decimal import Decimal
from urllib.error import URLError
from urllib.request import Request, urlopen

from django.conf import settings
from django.db import transaction
from django.db.models import Q, Sum
from django.utils import timezone

from core.constants import SUPPORTED_LANGUAGES
from tests.models import UserAnsweredTest, UserTestSession
from tests.quiz_services import get_quiz_progress

from .models import AtmosOrder, AtmosTransaction, SubscriptionPlan, TelegramUser


VALID_LANGUAGES = SUPPORTED_LANGUAGES


def split_full_name(full_name):
    parts = (full_name or "").strip().split(maxsplit=1)
    if not parts:
        return "", ""
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], parts[1]


def upsert_telegram_user(
    *,
    telegram_id,
    full_name="",
    username="",
    language="uz",
    phone_number="",
):
    first_name, last_name = split_full_name(full_name)
    defaults = {
        "full_name": full_name or "",
        "username": username or "",
        "language": language if language in VALID_LANGUAGES else "uz",
        "first_name": first_name,
        "last_name": last_name,
        "last_seen_at": timezone.now(),
    }
    if phone_number:
        defaults["phone_number"] = phone_number

    user, created = TelegramUser.objects.get_or_create(
        telegram_id=telegram_id,
        defaults=defaults,
    )
    if not created:
        update_fields = []
        for field, value in defaults.items():
            if field == "phone_number" and not phone_number:
                continue
            if getattr(user, field) != value:
                setattr(user, field, value)
                update_fields.append(field)
        if update_fields:
            user.save(update_fields=update_fields + ["updated_at"])
    return user


def get_user_premium_until(user):
    subscription = (
        user.premium_subscriptions.filter(is_active=True)
        .filter(Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now()))
        .order_by("-expires_at")
        .first()
    )
    return subscription.expires_at if subscription else None


def get_user_statistics(user):
    progress = get_quiz_progress(user)
    return {
        **progress,
        "premium_until": get_user_premium_until(user),
        "total_completions": UserAnsweredTest.objects.filter(user=user).count(),
    }


class AtmosPaymentService:
    def __init__(self):
        self.base_url = settings.ATMOS_BASE_URL.rstrip("/")
        self.store_id = settings.ATMOS_STORE_ID
        self.consumer_key = settings.ATMOS_CONSUMER_KEY
        self.consumer_secret = settings.ATMOS_CONSUMER_SECRET
        self.callback_url = settings.ATMOS_CALLBACK_URL
        self.return_url = settings.ATMOS_RETURN_URL

    def create_payment(self, order):
        payload = {
            "store_id": self.store_id,
            "amount": str(order.amount),
            "account": order.merchant_order_id,
            "callback_url": self.callback_url,
            "return_url": self.return_url,
        }
        if not self.base_url or not self.consumer_key or not self.consumer_secret:
            return {"payment_url": "", "raw": {"detail": "Atmos credentials are not configured."}}

        request = Request(
            f"{self.base_url}/merchant/pay/create",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "X-Consumer-Key": self.consumer_key,
                "X-Consumer-Secret": self.consumer_secret,
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=15) as response:
                raw = json.loads(response.read().decode("utf-8"))
        except (OSError, URLError, ValueError) as exc:
            raw = {"error": str(exc)}

        payment_url = (
            raw.get("payment_url")
            or raw.get("pay_url")
            or raw.get("redirect_url")
            or raw.get("url")
            or ""
        )
        return {"payment_url": payment_url, "raw": raw, "request": payload}


@transaction.atomic
def create_atmos_order(*, user, plan):
    order = AtmosOrder.objects.create(
        user=user,
        plan=plan,
        amount=plan.price,
        currency=plan.currency,
        status=AtmosOrder.Status.CREATED,
    )
    payment = AtmosPaymentService().create_payment(order)
    order.payment_url = payment["payment_url"]
    order.request_payload = payment.get("request", {})
    order.response_payload = payment["raw"]
    if order.payment_url:
        order.status = AtmosOrder.Status.PENDING
    order.save(
        update_fields=(
            "payment_url",
            "request_payload",
            "response_payload",
            "status",
            "updated_at",
        )
    )
    return order


def extract_callback_value(payload, *keys):
    for key in keys:
        value = payload.get(key)
        if value not in (None, ""):
            return value
    return ""


@transaction.atomic
def process_atmos_callback(payload):
    merchant_order_id = extract_callback_value(
        payload,
        "merchant_order_id",
        "account",
        "order_id",
        "store_order_id",
    )
    transaction_id = extract_callback_value(
        payload,
        "transaction_id",
        "trans_id",
        "payment_id",
        "id",
    )
    raw_status = str(
        extract_callback_value(payload, "status", "state", "payment_status")
    ).lower()
    raw_amount = extract_callback_value(payload, "amount", "total", "sum")

    order_query = None
    if merchant_order_id:
        order_query = Q(merchant_order_id=merchant_order_id) | Q(order_id=merchant_order_id)
    if transaction_id:
        transaction_query = Q(atmos_transaction_id=transaction_id)
        order_query = transaction_query if order_query is None else order_query | transaction_query
    if not order_query:
        return {"ok": False, "error": "order_not_found", "status": 404}

    order = (
        AtmosOrder.objects.select_for_update()
        .select_related("user", "plan")
        .filter(order_query)
        .first()
    )
    if not order:
        return {"ok": False, "error": "order_not_found", "status": 404}

    try:
        callback_amount = Decimal(str(raw_amount)) if raw_amount != "" else order.amount
    except Exception:
        callback_amount = Decimal("-1")
    if callback_amount != order.amount:
        transaction_status = AtmosTransaction.Status.FAILED
        order.status = AtmosOrder.Status.FAILED
        order.response_payload = payload
        order.save(update_fields=("status", "response_payload", "updated_at"))
        AtmosTransaction.objects.update_or_create(
            order=order,
            transaction_id=transaction_id or f"invalid-amount-{timezone.now().timestamp()}",
            defaults={
                "status": transaction_status,
                "amount": callback_amount,
                "currency": order.currency,
                "provider_payload": payload,
                "performed_at": timezone.now(),
            },
        )
        return {"ok": False, "error": "invalid_amount", "status": 400}

    success_statuses = {"paid", "success", "successful", "completed", "approved", "2"}
    failed_statuses = {"failed", "error", "declined", "rejected", "-1"}
    canceled_statuses = {"cancelled", "canceled", "cancel", "0"}

    if raw_status in success_statuses:
        transaction_status = AtmosTransaction.Status.SUCCESS
    elif raw_status in canceled_statuses:
        transaction_status = AtmosTransaction.Status.CANCELED
    elif raw_status in failed_statuses:
        transaction_status = AtmosTransaction.Status.FAILED
    else:
        transaction_status = AtmosTransaction.Status.INITIATED

    transaction_log, _ = AtmosTransaction.objects.update_or_create(
        order=order,
        transaction_id=transaction_id or f"callback-{timezone.now().timestamp()}",
        defaults={
            "status": transaction_status,
            "amount": order.amount,
            "currency": order.currency,
            "provider_payload": payload,
            "performed_at": timezone.now(),
        },
    )

    if transaction_status == AtmosTransaction.Status.SUCCESS:
        transaction_log.mark_as_success(payload=payload)
    elif transaction_status == AtmosTransaction.Status.CANCELED:
        order.status = AtmosOrder.Status.CANCELED
        order.response_payload = payload
        order.save(update_fields=("status", "response_payload", "updated_at"))
    elif transaction_status == AtmosTransaction.Status.FAILED:
        order.status = AtmosOrder.Status.FAILED
        order.response_payload = payload
        order.save(update_fields=("status", "response_payload", "updated_at"))

    return {"ok": True, "order": order, "transaction": transaction_log, "status": 200}


def get_admin_statistics():
    now = timezone.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    paid_orders = AtmosOrder.objects.filter(status=AtmosOrder.Status.PAID)
    total_revenue = paid_orders.aggregate(total=Sum("amount"))["total"] or 0
    today_revenue = paid_orders.filter(paid_at__gte=today_start).aggregate(total=Sum("amount"))["total"] or 0

    return {
        "total_users": TelegramUser.objects.count(),
        "premium_users": TelegramUser.objects.filter(
            premium_subscriptions__is_active=True,
            premium_subscriptions__starts_at__lte=now,
        )
        .filter(
            Q(premium_subscriptions__expires_at__isnull=True)
            | Q(premium_subscriptions__expires_at__gt=now)
        )
        .distinct()
        .count(),
        "blocked_users": TelegramUser.objects.filter(is_blocked=True).count(),
        "total_orders": AtmosOrder.objects.count(),
        "paid_orders": paid_orders.count(),
        "failed_orders": AtmosOrder.objects.filter(status=AtmosOrder.Status.FAILED).count(),
        "total_revenue": total_revenue,
        "today_revenue": today_revenue,
        "total_sessions": UserTestSession.objects.count(),
        "total_answers": UserTestAnswer.objects.count(),
    }


def get_active_plan(plan_id):
    return SubscriptionPlan.objects.filter(id=plan_id, is_active=True).first()
