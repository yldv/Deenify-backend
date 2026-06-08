import base64
import hashlib
import hmac
import json
import logging
from decimal import Decimal
from secrets import randbelow
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)

from django.conf import settings
from django.db import transaction
from django.db.models import Q, Sum
from django.utils import timezone

from core.constants import SUPPORTED_LANGUAGES
from tests.models import UserAnsweredTest
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
        self.terminal_id = settings.ATMOS_TERMINAL_ID
        self.consumer_key = settings.ATMOS_CONSUMER_KEY
        self.consumer_secret = settings.ATMOS_CONSUMER_SECRET
        self.callback_url = settings.ATMOS_CALLBACK_URL
        self.return_url = settings.ATMOS_RETURN_URL
        self.checkout_url = settings.ATMOS_CHECKOUT_URL.rstrip("/")

    def is_configured(self):
        return bool(
            self.base_url
            and self.store_id
            and self.consumer_key
            and self.consumer_secret
        )

    def missing_config_fields(self):
        missing = []
        if not self.store_id:
            missing.append("ATMOS_STORE_ID")
        if not self.consumer_key:
            missing.append("ATMOS_CONSUMER_KEY")
        if not self.consumer_secret:
            missing.append("ATMOS_CONSUMER_SECRET")
        return missing

    @staticmethod
    def _read_http_body(exc: HTTPError) -> dict:
        try:
            body = exc.read().decode("utf-8")
            return json.loads(body) if body else {"error": str(exc)}
        except Exception:
            return {"error": str(exc), "status": exc.code}

    def _request_json(self, path, *, payload=None, headers=None, method="POST"):
        data = None
        request_headers = headers or {}
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            request_headers = {"Content-Type": "application/json", **request_headers}

        request = Request(
            f"{self.base_url}{path}",
            data=data,
            headers=request_headers,
            method=method,
        )
        try:
            with urlopen(request, timeout=20) as response:
                body = response.read().decode("utf-8")
                return json.loads(body) if body else {}
        except HTTPError as exc:
            error_payload = self._read_http_body(exc)
            error_payload["http_status"] = exc.code
            raise ValueError(error_payload) from exc

    def get_access_token(self):
        credentials = f"{self.consumer_key}:{self.consumer_secret}".encode("utf-8")
        encoded_credentials = base64.b64encode(credentials).decode("ascii")
        request = Request(
            f"{self.base_url}/token?grant_type=client_credentials",
            data=b"grant_type=client_credentials",
            headers={
                "Authorization": f"Basic {encoded_credentials}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=20) as response:
                raw = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            error_payload = self._read_http_body(exc)
            raise ValueError(error_payload) from exc
        access_token = raw.get("access_token")
        if not access_token:
            raise ValueError(raw)
        return access_token, raw

    @staticmethod
    def _normalize_checkout_url(url: str) -> str:
        if not url:
            return url
        normalized = str(url).strip()
        normalized = normalized.replace("http://test-checkout.pays.uz", "https://test-checkout.pays.uz")
        normalized = normalized.replace("http://checkout.pays.uz", "https://checkout.pays.uz")
        return normalized

    def _default_checkout_base(self) -> str:
        if settings.ATMOS_TEST_MODE:
            return "https://test-checkout.pays.uz/invoice/get"
        return "https://checkout.pays.uz/invoice/get"

    def build_payment_url(self, transaction_id):
        checkout_base = self.checkout_url or self._default_checkout_base()
        checkout_base = self._normalize_checkout_url(checkout_base).rstrip("/")
        query = {
            "storeId": self.store_id,
            "transactionId": transaction_id,
        }
        if self.return_url:
            query["redirectLink"] = self.return_url
        return self._normalize_checkout_url(f"{checkout_base}?{urlencode(query)}")

    @staticmethod
    def _extract_payment_transaction_id(raw: dict) -> str:
        """Checkout/pre-apply use store_transaction.trans_id (see Atmos docs)."""
        store_transaction = raw.get("store_transaction") or {}
        for key in ("trans_id", "success_trans_id"):
            value = store_transaction.get(key)
            if value not in (None, ""):
                return str(value)
        for key in ("transaction_id", "trans_id", "transactionId"):
            value = raw.get(key)
            if value not in (None, ""):
                return str(value)
        return ""

    @staticmethod
    def _extract_payment_url(raw: dict) -> str:
        for key in ("paymentUrl", "payment_url", "pay_url"):
            value = raw.get(key)
            if value:
                return str(value)
        return ""

    @staticmethod
    def _extract_api_error(raw: dict) -> str:
        result = raw.get("result") or {}
        code = result.get("code")
        if code and str(code).upper() != "OK":
            description = str(result.get("description") or result.get("message") or code)
            return f"{description} (code: {code})"
        if raw.get("error"):
            return str(raw["error"])
        if raw.get("detail"):
            return str(raw["detail"])
        if raw.get("http_status"):
            return f"Atmos HTTP {raw['http_status']}"
        return ""

    @staticmethod
    def _normalize_store_id(store_id):
        # Atmos API examples use store_id as string (e.g. "10902").
        return str(store_id).strip()

    @staticmethod
    def _format_request_error(exc: Exception) -> str:
        if isinstance(exc, ValueError) and exc.args and isinstance(exc.args[0], dict):
            return AtmosPaymentService._extract_api_error(exc.args[0]) or str(exc)
        message = str(exc).lower()
        if "timed out" in message or "timeout" in message:
            return (
                "Cannot reach Atmos API (apigw.atmos.uz timeout). "
                "The server may need Uzbekistan network access or Atmos IP whitelist."
            )
        if "nodename nor servname" in message or "name or service not known" in message:
            return "Cannot resolve Atmos API host. Check ATMOS_BASE_URL."
        return str(exc)

    def create_payment(self, order):
        amount_tiyin = amount_to_tiyin(order.amount)
        payload = {
            "store_id": self._normalize_store_id(self.store_id),
            "amount": amount_tiyin,
            "account": order.merchant_order_id,
            "lang": "uz",
        }
        if self.terminal_id:
            payload["terminal_id"] = self.terminal_id

        if not self.is_configured():
            missing = ", ".join(self.missing_config_fields())
            detail = (
                f"Atmos is not configured. Set in .env: {missing}. "
                "Get test keys at https://partner-test.atmos.uz"
            )
            logger.warning("Atmos payment skipped: %s", detail)
            return {
                "payment_url": "",
                "transaction_id": "",
                "error": detail,
                "raw": {"detail": detail},
                "request": payload,
            }

        try:
            access_token, token_response = self.get_access_token()
            raw = self._request_json(
                "/merchant/pay/create",
                payload=payload,
                headers={"Authorization": f"Bearer {access_token}"},
            )
        except (OSError, URLError, KeyError, ValueError) as exc:
            error_detail = self._format_request_error(exc)
            logger.exception(
                "Atmos create payment failed for order=%s: %s",
                order.merchant_order_id,
                error_detail,
            )
            return {
                "payment_url": "",
                "transaction_id": "",
                "error": error_detail,
                "raw": {"error": error_detail},
                "request": payload,
            }

        api_error = self._extract_api_error(raw)
        transaction_id = self._extract_payment_transaction_id(raw)
        payment_url = self._normalize_checkout_url(self._extract_payment_url(raw))
        if not payment_url and transaction_id:
            payment_url = self.build_payment_url(transaction_id)
        elif payment_url and settings.ATMOS_TEST_MODE and "checkout.pays.uz" in payment_url:
            # Atmos sometimes returns production checkout for sandbox transactions.
            payment_url = self.build_payment_url(transaction_id)

        if api_error and not transaction_id:
            logger.error(
                "Atmos create payment rejected order=%s error=%s raw=%s",
                order.merchant_order_id,
                api_error,
                raw,
            )
            return {
                "payment_url": "",
                "transaction_id": "",
                "error": api_error,
                "raw": {**raw, "token_response": token_response},
                "request": payload,
            }

        if not payment_url:
            error = api_error or "Atmos did not return transaction_id."
            logger.error(
                "Atmos create payment without URL order=%s error=%s raw=%s",
                order.merchant_order_id,
                error,
                raw,
            )
            return {
                "payment_url": "",
                "transaction_id": transaction_id,
                "error": error,
                "raw": {**raw, "token_response": token_response},
                "request": payload,
            }

        return {
            "payment_url": payment_url,
            "transaction_id": transaction_id,
            "error": "",
            "raw": {**raw, "token_response": token_response},
            "request": payload,
        }


def amount_to_tiyin(amount):
    return int((Decimal(str(amount)) * Decimal("100")).quantize(Decimal("1")))


def generate_merchant_order_id(user):
    timestamp = timezone.now().strftime("%Y%m%d%H%M%S%f")
    suffix = f"{randbelow(1_000_000):06d}"
    return f"{timestamp}{user.telegram_id}{suffix}"[:64]


@transaction.atomic
def create_atmos_order(*, user, plan):
    order = AtmosOrder.objects.create(
        user=user,
        plan=plan,
        merchant_order_id=generate_merchant_order_id(user),
        amount=plan.price,
        currency=plan.currency,
        status=AtmosOrder.Status.CREATED,
    )
    payment = AtmosPaymentService().create_payment(order)
    order.payment_url = payment["payment_url"]
    order.atmos_transaction_id = payment["transaction_id"]
    order.request_payload = payment.get("request", {})
    order.response_payload = {
        **payment.get("raw", {}),
        **({"error": payment["error"]} if payment.get("error") else {}),
    }
    if order.payment_url:
        order.status = AtmosOrder.Status.PENDING
    order.save(
        update_fields=(
            "payment_url",
            "atmos_transaction_id",
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


def calculate_atmos_sign(payload):
    api_key = settings.ATMOS_API_KEY
    algorithm = settings.ATMOS_SIGN_ALGORITHM.lower()
    source = "".join(
        str(extract_callback_value(payload, key))
        for key in ("store_id", "transaction_id", "invoice", "amount")
    )
    source = f"{source}{api_key}"
    try:
        digest = hashlib.new(algorithm)
    except ValueError:
        digest = hashlib.sha256()
    digest.update(source.encode("utf-8"))
    return digest.hexdigest()


def validate_atmos_callback_sign(payload):
    expected_sign = extract_callback_value(payload, "sign")
    api_key = settings.ATMOS_API_KEY

    if not api_key:
        if settings.ATMOS_TEST_MODE:
            logger.warning("ATMOS_API_KEY is not set; accepting callback in ATMOS_TEST_MODE.")
            return True
        logger.error("ATMOS_API_KEY is not configured; Atmos callback rejected.")
        return False

    if not expected_sign:
        logger.warning("Atmos callback missing sign field.")
        return False

    calculated = calculate_atmos_sign(payload).lower()
    return hmac.compare_digest(str(expected_sign).lower(), calculated)


@transaction.atomic
def process_atmos_callback(payload):
    merchant_order_id = extract_callback_value(
        payload,
        "invoice",
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

    if not validate_atmos_callback_sign(payload):
        return {"ok": False, "error": "invalid_signature", "status": 400}

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
        callback_amount_tiyin = int(Decimal(str(raw_amount))) if raw_amount != "" else amount_to_tiyin(order.amount)
    except Exception:
        callback_amount_tiyin = -1
    if callback_amount_tiyin != amount_to_tiyin(order.amount):
        transaction_status = AtmosTransaction.Status.FAILED
        order.status = AtmosOrder.Status.FAILED
        order.response_payload = payload
        order.save(update_fields=("status", "response_payload", "updated_at"))
        AtmosTransaction.objects.update_or_create(
            order=order,
            transaction_id=transaction_id or f"invalid-amount-{timezone.now().timestamp()}",
            defaults={
                "status": transaction_status,
                "amount": Decimal(callback_amount_tiyin) / Decimal("100"),
                "currency": order.currency,
                "provider_payload": payload,
                "performed_at": timezone.now(),
            },
        )
        return {"ok": False, "error": "invalid_amount", "status": 400}

    success_statuses = {"paid", "success", "successful", "completed", "approved", "2"}
    failed_statuses = {"failed", "error", "declined", "rejected", "-1"}
    canceled_statuses = {"cancelled", "canceled", "cancel", "0"}

    if not raw_status or raw_status in success_statuses:
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
    }


def get_active_plan(plan_id):
    return SubscriptionPlan.objects.filter(id=plan_id, is_active=True).first()
