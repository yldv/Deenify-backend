import base64
import hashlib
import hmac
import json
import logging
import time
from decimal import Decimal
from secrets import randbelow
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from uuid import uuid4

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
    defaults["bot_is_active"] = True

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


def set_telegram_user_bot_active(*, telegram_id: int, bot_is_active: bool):
    user = TelegramUser.objects.filter(telegram_id=telegram_id).first()
    if not user or user.bot_is_active == bot_is_active:
        return user
    user.bot_is_active = bot_is_active
    user.save(update_fields=("bot_is_active", "updated_at"))
    return user


def get_active_premium_subscription(user):
    now = timezone.now()
    return (
        user.premium_subscriptions.filter(is_active=True, starts_at__lte=now)
        .filter(Q(expires_at__isnull=True) | Q(expires_at__gt=now))
        .select_related("plan")
        .order_by("-expires_at")
        .first()
    )


def get_user_premium_until(user):
    subscription = get_active_premium_subscription(user)
    return subscription.expires_at if subscription else None


def get_user_premium_starts_at(user):
    subscription = get_active_premium_subscription(user)
    return subscription.starts_at if subscription else None


def get_user_subscription_snapshot(user):
    free_limit = TelegramUser.FREE_TEST_LIMIT
    free_used = user.free_tests_taken
    base = {
        "free_used": free_used,
        "free_limit": free_limit,
        "plan": "",
        "starts_at": None,
        "expires_at": None,
        "pending_order_status": "",
    }

    if user.is_blocked:
        return {**base, "status": "blocked"}

    active = get_active_premium_subscription(user)
    if active:
        return {
            **base,
            "status": "active",
            "plan": active.plan.name,
            "starts_at": active.starts_at,
            "expires_at": active.expires_at,
        }

    pending_order = (
        user.atmos_orders.filter(
            status__in=(AtmosOrder.Status.CREATED, AtmosOrder.Status.PENDING),
        )
        .select_related("plan")
        .order_by("-created_at")
        .first()
    )
    if pending_order:
        return {
            **base,
            "status": "pending_payment",
            "plan": pending_order.plan.name,
            "pending_order_status": pending_order.status,
        }

    if free_used >= free_limit:
        return {**base, "status": "free_exhausted"}

    last_subscription = (
        user.premium_subscriptions.select_related("plan")
        .order_by("-expires_at", "-starts_at")
        .first()
    )
    if last_subscription:
        return {
            **base,
            "status": "expired",
            "plan": last_subscription.plan.name,
            "starts_at": last_subscription.starts_at,
            "expires_at": last_subscription.expires_at,
        }

    return {**base, "status": "free"}


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
        for host in (
            "checkout.atmos.uz",
            "dev-checkout.atmos.uz",
            "checkout.pays.uz",
        ):
            normalized = normalized.replace(f"http://{host}", f"https://{host}")
        return normalized

    @staticmethod
    def client_checkout_url(url: str) -> str:
        """Return payment URL as-is (merchant/pay uses test-checkout.pays.uz directly)."""
        return AtmosPaymentService._normalize_checkout_url(url)

    @staticmethod
    def _is_success_code(code) -> bool:
        if code in (None, ""):
            return True
        normalized = str(code).strip().upper()
        return normalized in {"OK", "0", "SUCCESS"}

    @staticmethod
    def _extract_payment_transaction_id(raw: dict) -> str:
        for key in ("payment_id", "transaction_id", "trans_id", "transactionId"):
            value = raw.get(key)
            if value not in (None, ""):
                return str(value)
        store_transaction = raw.get("store_transaction") or {}
        for key in ("trans_id", "success_trans_id"):
            value = store_transaction.get(key)
            if value not in (None, ""):
                return str(value)
        return ""

    @staticmethod
    def _extract_payment_url(raw: dict) -> str:
        for key in ("url", "paymentUrl", "payment_url", "pay_url"):
            value = raw.get(key)
            if value:
                return str(value)
        return ""

    @staticmethod
    def _extract_api_error(raw: dict) -> str:
        status = raw.get("status") or {}
        code = status.get("code")
        if code is not None and not AtmosPaymentService._is_success_code(code):
            description = str(status.get("description") or status.get("message") or code)
            locale = status.get("locale") or {}
            if not description and locale:
                description = str(locale.get("ru") or locale.get("uz") or locale.get("en") or code)
            return f"{description} (code: {code})"
        result = raw.get("result") or {}
        code = result.get("code")
        if code and not AtmosPaymentService._is_success_code(code):
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
    def _extract_checkout_transaction_id(raw: dict) -> str:
        store_transaction = raw.get("store_transaction") or {}
        for key in ("trans_id", "success_trans_id"):
            value = store_transaction.get(key)
            if value not in (None, ""):
                return str(value)
        return AtmosPaymentService._extract_payment_transaction_id(raw)

    def build_checkout_page_url(self, *, transaction_id: str, redirect_link: str = "") -> str:
        base = settings.ATMOS_CHECKOUT_PAGE_BASE.rstrip("/")
        params = {
            "storeId": self._normalize_store_id(self.store_id),
            "transactionId": str(transaction_id),
        }
        redirect = (redirect_link or self.return_url or "").strip()
        if redirect:
            params["redirectLink"] = redirect
        return f"{base}/invoice/get?{urlencode(params)}"

    def _build_merchant_pay_payload(self, order) -> dict:
        """Body for POST /merchant/pay/create (docs.atmos.uz)."""
        amount_tiyin = amount_to_tiyin(order.amount)
        payload = {
            "amount": amount_tiyin,
            "account": order.merchant_order_id,
            "store_id": self._normalize_store_id(self.store_id),
            "lang": "uz",
        }
        if self.terminal_id:
            payload["terminal_id"] = str(self.terminal_id).strip()
        return payload

    def _create_merchant_transaction(self, order, access_token):
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
        }
        payload = self._build_merchant_pay_payload(order)
        raw = self._request_json(
            "/merchant/pay/create",
            payload=payload,
            headers=headers,
        )
        return raw, payload

    def get_merchant_transaction(self, transaction_id: str) -> dict:
        access_token, _ = self.get_access_token()
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
        }
        payload = {
            "store_id": int(self._normalize_store_id(self.store_id)),
            "transaction_id": int(transaction_id),
        }
        return self._request_json(
            "/merchant/pay/get",
            payload=payload,
            headers=headers,
        )

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
        payload = self._build_merchant_pay_payload(order)

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
            raw, payload = self._create_merchant_transaction(order, access_token)
        except (OSError, URLError, KeyError, ValueError) as exc:
            error_detail = self._format_request_error(exc)
            logger.exception(
                "Atmos merchant/pay/create failed for order=%s: %s",
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
        checkout_transaction_id = self._extract_checkout_transaction_id(raw)
        redirect_link = (self.return_url or "").strip()
        payment_url = ""
        if checkout_transaction_id:
            payment_url = self.build_checkout_page_url(
                transaction_id=checkout_transaction_id,
                redirect_link=redirect_link,
            )

        if api_error and not checkout_transaction_id:
            logger.error(
                "Atmos merchant/pay/create rejected order=%s error=%s raw=%s",
                order.merchant_order_id,
                api_error,
                raw,
            )
            return {
                "payment_url": "",
                "transaction_id": checkout_transaction_id,
                "error": api_error,
                "raw": {**raw, "token_response": token_response},
                "request": payload,
            }

        if not payment_url:
            error = api_error or "Atmos did not return transaction id for checkout."
            logger.error(
                "Atmos merchant/pay/create without checkout URL order=%s error=%s raw=%s",
                order.merchant_order_id,
                error,
                raw,
            )
            return {
                "payment_url": "",
                "transaction_id": checkout_transaction_id,
                "error": error,
                "raw": {**raw, "token_response": token_response},
                "request": payload,
            }

        return {
            "payment_url": payment_url,
            "transaction_id": checkout_transaction_id,
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


PAYMENT_START_TOKEN_TTL = 3600


def _public_api_base_url() -> str:
    proxy_base = (settings.ATMOS_CHECKOUT_PROXY_BASE or "").strip().rstrip("/")
    if proxy_base:
        return proxy_base
    callback = (settings.ATMOS_CALLBACK_URL or "").strip().rstrip("/")
    if callback and "/api/" in callback:
        return callback.split("/api/", 1)[0]
    return ""


def build_payment_start_signature(*, telegram_id: int, plan_id: int, exp: int) -> str:
    secret = (settings.BOT_API_SECRET or "").strip()
    if not secret:
        return ""
    payload = f"{telegram_id}:{plan_id}:{exp}"
    return hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()


def verify_payment_start_signature(
    *, telegram_id: int, plan_id: int, exp: int, signature: str
) -> bool:
    if not signature or exp < int(time.time()):
        return False
    expected = build_payment_start_signature(
        telegram_id=telegram_id, plan_id=plan_id, exp=exp
    )
    if not expected:
        return False
    return hmac.compare_digest(expected, signature)


def build_payment_start_url(*, telegram_id: int, plan_id: int) -> str:
    base = _public_api_base_url()
    secret = (settings.BOT_API_SECRET or "").strip()
    if not base or not secret:
        return ""
    exp = int(time.time()) + PAYMENT_START_TOKEN_TTL
    signature = build_payment_start_signature(
        telegram_id=telegram_id, plan_id=plan_id, exp=exp
    )
    query = urlencode(
        {
            "telegram_id": telegram_id,
            "plan_id": plan_id,
            "exp": exp,
            "sig": signature,
        }
    )
    return f"{base}/api/v1/payments/atmos/start/?{query}"


def build_bot_payment_url(order):
    """Invoice URL from Atmos API, rewritten to our domain in sandbox (IP proxy)."""
    payment_url = (order.payment_url or "").strip()
    if not payment_url:
        return ""
    return AtmosPaymentService.client_checkout_url(payment_url)


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


def sync_atmos_order_payment(order) -> bool:
    """Poll merchant/pay/get and activate subscription when Atmos confirms payment."""
    if not order.atmos_transaction_id or order.status == AtmosOrder.Status.PAID:
        return order.status == AtmosOrder.Status.PAID

    service = AtmosPaymentService()
    if not service.is_configured():
        return False

    try:
        raw = service.get_merchant_transaction(order.atmos_transaction_id)
    except (OSError, URLError, ValueError) as exc:
        logger.warning(
            "Atmos merchant/pay/get failed order=%s: %s",
            order.merchant_order_id,
            exc,
        )
        return False

    store_transaction = raw.get("store_transaction") or {}
    if not store_transaction.get("confirmed"):
        return False

    transaction_id = str(
        store_transaction.get("success_trans_id")
        or store_transaction.get("trans_id")
        or order.atmos_transaction_id
    )
    AtmosTransaction.objects.update_or_create(
        order=order,
        transaction_id=transaction_id,
        defaults={
            "status": AtmosTransaction.Status.SUCCESS,
            "amount": order.amount,
            "currency": order.currency,
            "provider_payload": raw,
            "performed_at": timezone.now(),
        },
    )
    order.mark_as_paid(atmos_transaction_id=transaction_id, payload=raw)
    return True


@transaction.atomic
def process_atmos_callback(payload):
    """
    Atmos Callback API (docs.atmos.uz): validate invoice before payment.
    Response must be {"status": 1, "message": "..."} to allow payment.
    """
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
    raw_amount = extract_callback_value(payload, "amount", "total", "sum")

    if not validate_atmos_callback_sign(payload):
        return {
            "ok": False,
            "atmos_status": 0,
            "message": "Invalid signature",
            "http_status": 200,
        }

    order_query = None
    if merchant_order_id:
        order_query = Q(merchant_order_id=merchant_order_id) | Q(order_id=merchant_order_id)
    if transaction_id:
        transaction_query = Q(atmos_transaction_id=str(transaction_id))
        order_query = transaction_query if order_query is None else order_query | transaction_query
    if not order_query:
        return {
            "ok": False,
            "atmos_status": 0,
            "message": "Invoice not found",
            "http_status": 200,
        }

    order = (
        AtmosOrder.objects.select_for_update()
        .select_related("user", "plan")
        .filter(order_query)
        .first()
    )
    if not order:
        return {
            "ok": False,
            "atmos_status": 0,
            "message": "Invoice not found",
            "http_status": 200,
        }

    try:
        callback_amount_tiyin = int(Decimal(str(raw_amount))) if raw_amount != "" else amount_to_tiyin(order.amount)
    except Exception:
        callback_amount_tiyin = -1
    if callback_amount_tiyin != amount_to_tiyin(order.amount):
        return {
            "ok": False,
            "atmos_status": 0,
            "message": "Invalid amount",
            "http_status": 200,
        }

    if order.status == AtmosOrder.Status.PAID:
        return {
            "ok": True,
            "atmos_status": 1,
            "message": "Successfully",
            "http_status": 200,
            "order": order,
        }

    if order.status not in (AtmosOrder.Status.CREATED, AtmosOrder.Status.PENDING):
        return {
            "ok": False,
            "atmos_status": 0,
            "message": "Invoice not available",
            "http_status": 200,
        }

    update_fields = ["response_payload", "updated_at"]
    order.response_payload = payload
    if transaction_id and str(order.atmos_transaction_id) != str(transaction_id):
        order.atmos_transaction_id = str(transaction_id)
        update_fields.append("atmos_transaction_id")
    if order.status == AtmosOrder.Status.CREATED:
        order.status = AtmosOrder.Status.PENDING
        update_fields.append("status")
    order.save(update_fields=update_fields)

    return {
        "ok": True,
        "atmos_status": 1,
        "message": "Successfully",
        "http_status": 200,
        "order": order,
    }


def get_admin_statistics():
    now = timezone.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    paid_orders = AtmosOrder.objects.filter(status=AtmosOrder.Status.PAID)
    total_revenue = paid_orders.aggregate(total=Sum("amount"))["total"] or 0
    today_revenue = paid_orders.filter(paid_at__gte=today_start).aggregate(total=Sum("amount"))["total"] or 0

    return {
        "total_users": TelegramUser.objects.count(),
        "active_bot_users": TelegramUser.objects.filter(bot_is_active=True).count(),
        "inactive_bot_users": TelegramUser.objects.filter(bot_is_active=False).count(),
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
