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

from .models import (
    AtmosOrder,
    AtmosTransaction,
    BoundCard,
    SubscriptionPlan,
    TelegramUser,
    UserPremiumSubscription,
)


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
    referred_by=None,
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
    if referred_by:
        _attach_referrer(user, referred_by)
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


def _attach_referrer(user, referrer_telegram_id):
    """Link a user to the inviter.

    Works for both brand-new and already-registered users, as long as the user
    does not have an inviter yet and has not paid yet (so they still count as a
    fresh referral whose first payment can reward the inviter). Never self-links.
    """
    if user.referred_by_id:
        return
    try:
        referrer_telegram_id = int(referrer_telegram_id)
    except (TypeError, ValueError):
        return
    if referrer_telegram_id == user.telegram_id:
        return
    # Already-converted users can't be (re)attributed to a new inviter.
    if user.referral_rewarded:
        return
    if user.atmos_orders.filter(status=AtmosOrder.Status.PAID).exists():
        return
    referrer = TelegramUser.objects.filter(telegram_id=referrer_telegram_id).first()
    if not referrer:
        return
    user.referred_by = referrer
    user.save(update_fields=("referred_by", "updated_at"))


def build_referral_link(user) -> str:
    username = (getattr(settings, "BOT_USERNAME", "") or "").strip().lstrip("@")
    if not username:
        return ""
    return f"https://t.me/{username}?start=ref_{user.telegram_id}"


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
            "plan": active.plan.name if active.plan else "Premium",
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
            "plan": last_subscription.plan.name if last_subscription.plan else "Premium",
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

    def _request_json(self, path, *, payload=None, headers=None, method="POST", timeout=None):
        if timeout is None:
            timeout = settings.ATMOS_REQUEST_TIMEOUT
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
            with urlopen(request, timeout=timeout) as response:
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
            with urlopen(request, timeout=settings.ATMOS_REQUEST_TIMEOUT) as response:
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
        """Normalize checkout URL (Atmos: test-checkout.pays.uz, no dev-checkout proxy)."""
        return AtmosPaymentService._normalize_checkout_url(url)

    def _payment_flow(self) -> str:
        flow = (settings.ATMOS_PAYMENT_FLOW or "").strip().lower()
        if flow in {"merchant", "invoice"}:
            return flow
        return "merchant"

    def _public_checkout_base(self) -> str:
        if settings.ATMOS_TEST_MODE:
            return "https://test-checkout.pays.uz"
        return "https://checkout.pays.uz"

    def _merchant_headers(self, access_token: str) -> dict:
        # Outbound merchant/partner API: Bearer token only (docs.atmos.uz).
        # ATMOS_API_KEY is for validating incoming callbacks, not outbound requests.
        return {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
        }

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
            code = raw["http_status"]
            if code == 403:
                return (
                    "Atmos denied access (HTTP 403). "
                    "Ask Atmos to whitelist your server IP and enable Merchant API "
                    "for this Store/Terminal."
                )
            return f"Atmos HTTP {code}"
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
        base = self._public_checkout_base()
        params = {
            "storeId": self._normalize_store_id(self.store_id),
            "transactionId": str(transaction_id),
        }
        redirect = (redirect_link or self.return_url or "").strip()
        if redirect:
            params["redirectLink"] = redirect
        return self.client_checkout_url(f"{base}/invoice/get?{urlencode(params)}")

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
        redirect = (self.return_url or "").strip()
        if redirect:
            payload["redirect_link"] = redirect
        return payload

    def _create_merchant_transaction(self, order, access_token):
        payload = self._build_merchant_pay_payload(order)
        raw = self._request_json(
            "/merchant/pay/create",
            payload=payload,
            headers=self._merchant_headers(access_token),
        )
        return raw, payload

    @staticmethod
    def _ofd_item_details():
        return [
            {"name": "package_code", "values": "1"},
            {"name": "mark_code", "values": "0"},
            {"name": "tin", "values": "0"},
            {"name": "discount", "values": "0"},
            {"name": "quantity", "values": "1"},
        ]

    def _build_invoice_item(self, *, plan_name: str, amount_tiyin: int) -> dict:
        return {
            "items_id": "1",
            "code": "premium",
            "name": str(plan_name)[:255],
            "amount": amount_tiyin,
            "quantity": 1,
            "details": self._ofd_item_details(),
        }

    def _build_invoice_payload(self, order, *, use_doc_items_field: bool = False):
        amount_tiyin = amount_to_tiyin(order.amount)
        plan_name = "Deenify Premium"
        if getattr(order, "plan", None):
            plan_name = order.plan.name or plan_name
        request_id = (order.merchant_order_id or order.order_id or uuid4().hex)[:64]
        item = self._build_invoice_item(plan_name=plan_name, amount_tiyin=amount_tiyin)
        payload = {
            "request_id": request_id,
            "store_id": int(self._normalize_store_id(self.store_id)),
            "account": order.merchant_order_id,
            "amount": amount_tiyin,
            "success_url": self.return_url or settings.ATMOS_SUCCESS_REDIRECT_URL,
            "expiration_time": settings.ATMOS_INVOICE_EXPIRATION_SECONDS,
        }
        if use_doc_items_field:
            payload["items"] = [item]
        else:
            payload["payment_items"] = [item]
        return payload

    def _create_invoice(self, order, access_token):
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
        }
        raw = {}
        payload = self._build_invoice_payload(order)
        for use_doc_items in (False, True):
            payload = self._build_invoice_payload(order, use_doc_items_field=use_doc_items)
            raw = self._request_json(
                "/checkout/invoice/create",
                payload=payload,
                headers=headers,
            )
            api_error = self._extract_api_error(raw)
            payment_url = self._extract_payment_url(raw)
            if payment_url or not api_error:
                return raw, payload
            if str(api_error).find("-999998") == -1:
                return raw, payload
        return raw, payload

    def get_merchant_transaction(self, transaction_id: str) -> dict:
        access_token, _ = self.get_access_token()
        payload = {
            "store_id": int(self._normalize_store_id(self.store_id)),
            "transaction_id": int(transaction_id),
        }
        return self._request_json(
            "/merchant/pay/get",
            payload=payload,
            headers=self._merchant_headers(access_token),
        )

    def pre_apply(self, *, transaction_id, card_number=None, expiry=None, card_token=None) -> dict:
        """POST /merchant/pay/pre-apply.

        With card_number+expiry: Atmos sends an OTP via SMS (one-time payment).
        With card_token (bound card): no SMS is sent (recurring/auto payment).
        """
        access_token, _ = self.get_access_token()
        payload = {
            "store_id": int(self._normalize_store_id(self.store_id)),
            "transaction_id": int(transaction_id),
        }
        if card_token:
            payload["card_token"] = str(card_token).strip()
        else:
            payload["card_number"] = str(card_number).replace(" ", "").strip()
            payload["expiry"] = str(expiry).strip()
        return self._request_json(
            "/merchant/pay/pre-apply",
            payload=payload,
            headers=self._merchant_headers(access_token),
        )

    def bind_card_init(self, *, card_number, expiry) -> dict:
        """POST /partner/bind-card/init: start linking a card; Atmos sends an SMS code."""
        access_token, _ = self.get_access_token()
        payload = {
            "card_number": str(card_number).replace(" ", "").strip(),
            "expiry": str(expiry).strip(),
        }
        return self._request_json(
            "/partner/bind-card/init",
            payload=payload,
            headers=self._merchant_headers(access_token),
        )

    def bind_card_confirm(self, *, transaction_id, otp) -> dict:
        """POST /partner/bind-card/confirm: confirm with SMS code, returns card_token."""
        access_token, _ = self.get_access_token()
        otp_value = str(otp).strip()
        payload = {
            "transaction_id": int(transaction_id),
            "otp": otp_value,
        }
        return self._request_json(
            "/partner/bind-card/confirm",
            payload=payload,
            headers=self._merchant_headers(access_token),
        )

    def remove_card(self, *, card_id, card_token) -> dict:
        """POST /partner/remove-card: cancel a previously linked card token."""
        access_token, _ = self.get_access_token()
        payload = {
            "id": int(card_id) if str(card_id).isdigit() else card_id,
            "token": str(card_token).strip(),
        }
        return self._request_json(
            "/partner/remove-card",
            payload=payload,
            headers=self._merchant_headers(access_token),
        )

    def apply(self, *, transaction_id, otp) -> dict:
        """POST /merchant/pay/apply: confirm with OTP and charge the card."""
        access_token, _ = self.get_access_token()
        otp_value = str(otp).strip()
        payload = {
            "otp": int(otp_value) if otp_value.isdigit() else otp_value,
            "store_id": int(self._normalize_store_id(self.store_id)),
            "transaction_id": int(transaction_id),
        }
        return self._request_json(
            "/merchant/pay/apply",
            payload=payload,
            headers=self._merchant_headers(access_token),
            timeout=settings.ATMOS_APPLY_TIMEOUT,
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
                "Atmos API did not respond in time. "
                "If this happens on apply, increase ATMOS_APPLY_TIMEOUT in .env."
            )
        if "nodename nor servname" in message or "name or service not known" in message:
            return "Cannot resolve Atmos API host. Check ATMOS_BASE_URL."
        return str(exc)

    def create_payment(self, order):
        if not self.is_configured():
            missing = ", ".join(self.missing_config_fields())
            detail = (
                f"Atmos is not configured. Set in .env: {missing}. "
                + (
                    "Get prod keys at https://partner.atmos.uz"
                    if not settings.ATMOS_TEST_MODE
                    else "Get test keys at https://partner-test.atmos.uz"
                )
            )
            logger.warning("Atmos payment skipped: %s", detail)
            return {
                "payment_url": "",
                "transaction_id": "",
                "error": detail,
                "raw": {"detail": detail},
                "request": {},
            }
        if self._payment_flow() == "invoice":
            return self._create_payment_invoice(order)
        return self._create_payment_merchant(order)

    def _create_payment_merchant(self, order):
        payload = self._build_merchant_pay_payload(order)
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

    def _create_payment_invoice(self, order):
        payload = self._build_invoice_payload(order)
        try:
            access_token, token_response = self.get_access_token()
            raw, payload = self._create_invoice(order, access_token)
        except (OSError, URLError, KeyError, ValueError) as exc:
            error_detail = self._format_request_error(exc)
            logger.exception(
                "Atmos checkout/invoice/create failed for order=%s: %s",
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
        payment_url = self.client_checkout_url(self._extract_payment_url(raw))

        if api_error and not payment_url:
            logger.error(
                "Atmos invoice create rejected order=%s error=%s raw=%s",
                order.merchant_order_id,
                api_error,
                raw,
            )
            return {
                "payment_url": "",
                "transaction_id": transaction_id,
                "error": api_error,
                "raw": {**raw, "token_response": token_response},
                "request": payload,
            }

        if not payment_url:
            error = api_error or "Atmos did not return payment url."
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
    _init_atmos_trace(
        order,
        step="merchant/pay/create",
        request=payment.get("request", {}),
        response=payment.get("raw", {}),
        error=payment.get("error") or "",
    )
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


CARD_SESSION_TOKEN_TTL = 900


def build_card_session_token(*, order_id: str, exp: int) -> str:
    secret = (settings.BOT_API_SECRET or "").strip()
    if not secret:
        return ""
    payload = f"{order_id}:{exp}"
    return hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()


def verify_card_session_token(*, order_id: str, exp: int, token: str) -> bool:
    if not token or exp < int(time.time()):
        return False
    expected = build_card_session_token(order_id=order_id, exp=exp)
    if not expected:
        return False
    return hmac.compare_digest(expected, token)


def start_card_payment(*, user, plan):
    """Create Atmos transaction (merchant/pay/create) for the card form."""
    order = create_atmos_order(user=user, plan=plan)
    error = ""
    raw = order.response_payload or {}
    if isinstance(raw, dict) and raw.get("error"):
        error = str(raw["error"])
    if not order.atmos_transaction_id:
        error = error or "Atmos did not return transaction id."
    return order, error


def submit_card_for_payment(*, order, card_number, expiry):
    """Send card to Atmos pre-apply; Atmos sends OTP via SMS."""
    service = AtmosPaymentService()
    if not service.is_configured() or not order.atmos_transaction_id:
        return {"ok": False, "error": "Payment is not configured."}
    try:
        raw = service.pre_apply(
            transaction_id=order.atmos_transaction_id,
            card_number=card_number,
            expiry=expiry,
        )
    except (OSError, URLError, ValueError) as exc:
        return {"ok": False, "error": service._format_request_error(exc)}
    api_error = service._extract_api_error(raw)
    if api_error:
        return {"ok": False, "error": api_error, "raw": raw}
    return {"ok": True, "raw": raw}


def confirm_card_payment(*, order, otp):
    """Confirm Atmos transaction with OTP (apply); activate subscription on success."""
    service = AtmosPaymentService()
    if not service.is_configured() or not order.atmos_transaction_id:
        return {"ok": False, "error": "Payment is not configured."}
    try:
        raw = service.apply(transaction_id=order.atmos_transaction_id, otp=otp)
    except (OSError, URLError, ValueError) as exc:
        return {"ok": False, "error": service._format_request_error(exc)}
    api_error = service._extract_api_error(raw)
    store_transaction = raw.get("store_transaction") or {}
    confirmed = bool(store_transaction.get("confirmed")) or service._is_success_code(
        (raw.get("result") or {}).get("code")
    )
    if api_error or not confirmed:
        return {"ok": False, "error": api_error or "Payment was not confirmed.", "raw": raw}

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
    after_order_paid(order)
    return {"ok": True, "raw": raw}


def _notify_payment_success_safe(order):
    """Send the Telegram success notification without breaking the payment flow."""
    try:
        from .notifications import notify_payment_success

        notify_payment_success(order)
    except Exception:  # noqa: BLE001
        logger.exception(
            "Payment success notification failed order=%s",
            getattr(order, "merchant_order_id", None) or getattr(order, "pk", None),
        )


def after_order_paid(order):
    """Run side effects after an order is marked paid: referral reward + notification."""
    try:
        grant_referral_reward(order)
    except Exception:  # noqa: BLE001
        logger.exception(
            "Referral reward failed order=%s",
            getattr(order, "merchant_order_id", None) or getattr(order, "pk", None),
        )
    _notify_payment_success_safe(order)


# ---------------------------------------------------------------------------
# Card binding + recurring (token) payments
# ---------------------------------------------------------------------------


def start_card_binding(*, card_number, expiry):
    """Begin Atmos card linking: /partner/bind-card/init (Atmos sends an SMS code)."""
    service = AtmosPaymentService()
    if not service.is_configured():
        return {"ok": False, "error": "Payment is not configured."}
    logger.info("Atmos bind-card/init: requesting card link (masked card ****%s)", str(card_number)[-4:])
    try:
        raw = service.bind_card_init(card_number=card_number, expiry=expiry)
    except (OSError, URLError, ValueError) as exc:
        logger.warning("Atmos bind-card/init failed: %s", service._format_request_error(exc))
        return {"ok": False, "error": service._format_request_error(exc)}
    api_error = service._extract_api_error(raw)
    transaction_id = raw.get("transaction_id")
    if api_error or not transaction_id:
        logger.warning("Atmos bind-card/init rejected: error=%s raw=%s", api_error, raw)
        return {"ok": False, "error": api_error or "Card binding could not be started.", "raw": raw}
    logger.info("Atmos bind-card/init OK: transaction_id=%s", transaction_id)
    return {
        "ok": True,
        "transaction_id": str(transaction_id),
        "phone": raw.get("phone", ""),
        "raw": raw,
    }


def confirm_card_binding(*, user, transaction_id, otp):
    """Confirm card linking with the SMS code and persist a BoundCard for the user."""
    service = AtmosPaymentService()
    if not service.is_configured():
        return {"ok": False, "error": "Payment is not configured."}
    logger.info("Atmos bind-card/confirm: transaction_id=%s", transaction_id)
    try:
        raw = service.bind_card_confirm(transaction_id=transaction_id, otp=otp)
    except (OSError, URLError, ValueError) as exc:
        logger.warning("Atmos bind-card/confirm failed: %s", service._format_request_error(exc))
        return {"ok": False, "error": service._format_request_error(exc)}
    api_error = service._extract_api_error(raw)
    data = raw.get("data") or {}
    card_token = data.get("card_token")
    if api_error or not card_token:
        logger.warning("Atmos bind-card/confirm rejected: error=%s raw=%s", api_error, raw)
        return {"ok": False, "error": api_error or "Card binding failed.", "raw": raw}
    logger.info("Atmos bind-card/confirm OK: card_id=%s pan=%s", data.get("card_id"), data.get("pan"))

    with transaction.atomic():
        bound = BoundCard.objects.create(
            user=user,
            card_id=str(data.get("card_id") or ""),
            card_token=str(card_token),
            masked_pan=str(data.get("pan") or ""),
            expiry=str(data.get("expiry") or ""),
            card_holder=str(data.get("card_holder") or ""),
            phone=str(data.get("phone") or ""),
            is_active=True,
        )
        BoundCard.objects.filter(user=user, is_active=True).exclude(pk=bound.pk).update(
            is_active=False
        )
    return {"ok": True, "bound_card": bound, "raw": raw}


def charge_subscription(*, user, plan, bound_card, is_auto_renewal=False):
    """Charge a bound card for a subscription period via merchant/pay/{create,pre-apply,apply}."""
    service = AtmosPaymentService()
    if not service.is_configured():
        return {"ok": False, "error": "Payment is not configured."}
    if not bound_card or not bound_card.card_token:
        return {"ok": False, "error": "No bound card available."}

    order = create_atmos_order(user=user, plan=plan)
    order.bound_card = bound_card
    order.is_auto_renewal = is_auto_renewal
    order.save(update_fields=("bound_card", "is_auto_renewal", "updated_at"))
    logger.info(
        "Atmos token charge: user=%s order=%s plan=%s auto=%s card_id=%s",
        user.telegram_id,
        order.merchant_order_id,
        plan.id,
        is_auto_renewal,
        bound_card.card_id,
    )

    if not order.atmos_transaction_id:
        error = ""
        raw = order.response_payload or {}
        if isinstance(raw, dict) and raw.get("error"):
            error = str(raw["error"])
        return {"ok": False, "error": error or "Atmos did not return transaction id.", "order": order}

    pre_request = {
        "store_id": int(service._normalize_store_id(service.store_id)),
        "transaction_id": int(order.atmos_transaction_id),
        "card_token": _mask_atmos_secret(bound_card.card_token),
    }
    try:
        pre_raw = service.pre_apply(
            transaction_id=order.atmos_transaction_id,
            card_token=bound_card.card_token,
        )
    except (OSError, URLError, ValueError) as exc:
        return {"ok": False, "error": service._format_request_error(exc), "order": order}
    _append_atmos_trace(
        order,
        step="merchant/pay/pre-apply",
        request=pre_request,
        response=pre_raw,
    )
    order.save(update_fields=("response_payload", "updated_at"))
    pre_error = service._extract_api_error(pre_raw)
    if pre_error:
        logger.warning(
            "Atmos pre-apply rejected order=%s error=%s raw=%s",
            order.merchant_order_id,
            pre_error,
            pre_raw,
        )
        _mark_order_failed(order, pre_raw)
        return {"ok": False, "error": pre_error, "order": order, "raw": pre_raw}

    apply_request = {
        "store_id": int(service._normalize_store_id(service.store_id)),
        "transaction_id": int(order.atmos_transaction_id),
        "otp": _mask_atmos_secret(settings.ATMOS_TOKEN_PAYMENT_OTP),
    }
    try:
        raw = service.apply(
            transaction_id=order.atmos_transaction_id,
            otp=settings.ATMOS_TOKEN_PAYMENT_OTP,
        )
    except (OSError, URLError, ValueError) as exc:
        return {"ok": False, "error": service._format_request_error(exc), "order": order}
    _append_atmos_trace(
        order,
        step="merchant/pay/apply",
        request=apply_request,
        response=raw,
    )

    api_error = service._extract_api_error(raw)
    store_transaction = raw.get("store_transaction") or {}
    confirmed = bool(store_transaction.get("confirmed")) or service._is_success_code(
        (raw.get("result") or {}).get("code")
    )
    if api_error or not confirmed:
        logger.warning(
            "Atmos apply rejected order=%s error=%s raw=%s",
            order.merchant_order_id,
            api_error,
            raw,
        )
        _mark_order_failed(order, raw)
        return {"ok": False, "error": api_error or "Payment was not confirmed.", "order": order, "raw": raw}

    order.save(update_fields=("response_payload", "updated_at"))
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
    subscription = order.mark_as_paid(
        atmos_transaction_id=transaction_id,
        payload=_order_trace_payload(order),
    )
    after_order_paid(order)
    return {"ok": True, "order": order, "subscription": subscription, "raw": raw}


def _mask_atmos_secret(value) -> str:
    text = str(value or "").strip()
    if len(text) <= 8:
        return "***"
    return f"{text[:4]}...{text[-4:]}"


def _order_trace_payload(order) -> dict:
    if isinstance(order.response_payload, dict):
        return dict(order.response_payload)
    return {}


def _init_atmos_trace(order, *, step: str, request: dict, response: dict, error: str = "") -> None:
    payload = {
        "atmos_trace": [{"step": step, "request": request, "response": response}],
        "last_step": step,
    }
    if error:
        payload["error"] = error
    order.response_payload = payload


def _append_atmos_trace(order, *, step: str, request: dict, response: dict) -> None:
    payload = _order_trace_payload(order)
    trace = list(payload.get("atmos_trace") or [])
    trace.append({"step": step, "request": request, "response": response})
    payload["atmos_trace"] = trace
    payload["last_step"] = step
    order.response_payload = payload


def _mark_order_failed(order, payload):
    order.status = AtmosOrder.Status.FAILED
    existing = _order_trace_payload(order)
    if payload:
        existing["last_error_response"] = payload
        if isinstance(payload, dict) and payload.get("result"):
            existing["result"] = payload["result"]
    order.response_payload = existing
    order.save(update_fields=("status", "response_payload", "updated_at"))


def remove_bound_card(user):
    """Remove the active bound card (Atmos /partner/remove-card) and stop auto-renewal."""
    service = AtmosPaymentService()
    card = (
        BoundCard.objects.filter(user=user, is_active=True)
        .order_by("-created_at")
        .first()
    )
    error = ""
    if card and service.is_configured():
        logger.info(
            "Atmos remove-card: user=%s card_id=%s", user.telegram_id, card.card_id
        )
        try:
            raw = service.remove_card(card_id=card.card_id, card_token=card.card_token)
            error = service._extract_api_error(raw)
            if error:
                logger.warning("Atmos remove-card rejected user=%s: %s", user.telegram_id, error)
            else:
                logger.info("Atmos remove-card OK: user=%s card_id=%s", user.telegram_id, card.card_id)
        except (OSError, URLError, ValueError) as exc:
            error = service._format_request_error(exc)
            logger.warning("Atmos remove-card failed user=%s: %s", user.telegram_id, error)
    elif not card:
        logger.info("Cancel subscription: no active bound card for user=%s (nothing to remove)", user.telegram_id)

    if card:
        card.mark_removed()
    UserPremiumSubscription.objects.filter(user=user, is_active=True, auto_renew=True).update(
        auto_renew=False
    )
    return {"ok": not error, "removed": bool(card), "error": error}


# ---------------------------------------------------------------------------
# Referral rewards
# ---------------------------------------------------------------------------


def _plan_is_yearly(plan):
    if not plan:
        return False
    return plan.period == SubscriptionPlan.BillingPeriod.YEAR


def extend_premium_days(*, user, days, source=UserPremiumSubscription.Source.REFERRAL):
    """Add `days` of premium to a user.

    If the user already has a current active subscription, its expiry is pushed
    forward in place so the visible "premium until" date reflects the bonus
    immediately. Otherwise a fresh bonus period is created starting now.
    """
    if days <= 0:
        return None
    from datetime import timedelta

    now = timezone.now()
    with transaction.atomic():
        active = (
            UserPremiumSubscription.objects.select_for_update()
            .filter(user=user, is_active=True, starts_at__lte=now)
            .filter(Q(expires_at__isnull=True) | Q(expires_at__gt=now))
            .order_by("-expires_at")
            .first()
        )
        if active:
            if active.expires_at is None:
                return active  # already lifetime, nothing to add
            active.expires_at = active.expires_at + timedelta(days=days)
            active.save(update_fields=("expires_at", "updated_at"))
            return active
        return UserPremiumSubscription.objects.create(
            user=user,
            plan=None,
            starts_at=now,
            expires_at=now + timedelta(days=days),
            is_active=True,
            auto_renew=False,
            source=source,
        )


def grant_referral_reward(order):
    """Reward the inviter when the invited user makes their FIRST successful payment."""
    user = order.user
    referrer_id = getattr(user, "referred_by_id", None)
    if not referrer_id or user.referral_rewarded:
        return None

    days = (
        settings.ATMOS_REFERRAL_BONUS_DAYS_YEARLY
        if _plan_is_yearly(order.plan)
        else settings.ATMOS_REFERRAL_BONUS_DAYS_MONTHLY
    )

    with transaction.atomic():
        locked_user = TelegramUser.objects.select_for_update().get(pk=user.pk)
        if locked_user.referral_rewarded or not locked_user.referred_by_id:
            return None
        referrer = TelegramUser.objects.filter(pk=locked_user.referred_by_id).first()
        if not referrer:
            return None
        locked_user.referral_rewarded = True
        locked_user.save(update_fields=("referral_rewarded", "updated_at"))
        extend_premium_days(user=referrer, days=days)

    try:
        from .notifications import notify_referral_reward

        notify_referral_reward(referrer=referrer, invited_user=user, days=days)
    except Exception:  # noqa: BLE001
        logger.exception("Referral reward notification failed referrer=%s", referrer.pk)
    return referrer


def get_referral_stats(user):
    """Counts for the referral panel: invited users, paying ones, bonus days earned."""
    invited_qs = TelegramUser.objects.filter(referred_by=user)
    paid_count = invited_qs.filter(referral_rewarded=True).count()
    bonus_days = (
        UserPremiumSubscription.objects.filter(
            user=user, source=UserPremiumSubscription.Source.REFERRAL
        )
        .count()
    )
    monthly = settings.ATMOS_REFERRAL_BONUS_DAYS_MONTHLY
    yearly = settings.ATMOS_REFERRAL_BONUS_DAYS_YEARLY
    return {
        "invited_count": invited_qs.count(),
        "paid_count": paid_count,
        "reward_subscriptions": bonus_days,
        "bonus_days_monthly": monthly,
        "bonus_days_yearly": yearly,
    }


def parse_atmos_callback_payload(request) -> dict:
    """Normalize Atmos callback body (JSON object, raw JSON string, or wrapped field)."""
    data = getattr(request, "data", None)
    if isinstance(data, dict) and data:
        if not any(
            key in data
            for key in ("store_id", "transaction_id", "sign", "account", "invoice", "amount")
        ):
            for value in data.values():
                if isinstance(value, str) and value.strip().startswith("{"):
                    try:
                        parsed = json.loads(value)
                        if isinstance(parsed, dict):
                            return parsed
                    except json.JSONDecodeError:
                        continue
        return data
    if isinstance(data, str) and data.strip():
        try:
            parsed = json.loads(data)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass
    body = getattr(request, "body", b"") or b""
    if body:
        try:
            parsed = json.loads(body.decode("utf-8"))
            if isinstance(parsed, dict):
                return parsed
        except (UnicodeDecodeError, json.JSONDecodeError):
            pass
    return {}


def _atmos_callback_ok_message() -> str:
    return settings.ATMOS_CALLBACK_SUCCESS_MESSAGE


def extract_callback_value(payload, *keys):
    for key in keys:
        value = payload.get(key)
        if value not in (None, ""):
            return value
    return ""


def _callback_invoice_for_sign(payload) -> str:
    """Atmos callback: invoice id is sent as ``invoice`` or ``account``."""
    return str(
        extract_callback_value(
            payload,
            "invoice",
            "account",
            "merchant_order_id",
            "order_id",
            "store_order_id",
        )
    )


def calculate_atmos_sign(payload):
    api_key = settings.ATMOS_API_KEY
    algorithm = settings.ATMOS_SIGN_ALGORITHM.lower()
    source = "".join(
        [
            str(extract_callback_value(payload, "store_id")),
            str(extract_callback_value(payload, "transaction_id")),
            _callback_invoice_for_sign(payload),
            str(extract_callback_value(payload, "amount")),
            api_key,
        ]
    )
    try:
        digest = hashlib.new(algorithm)
    except ValueError:
        digest = hashlib.md5()
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
    if hmac.compare_digest(str(expected_sign).lower(), calculated):
        return True

    logger.warning(
        "Atmos callback signature mismatch store_id=%s transaction_id=%s account=%s "
        "algorithm=%s received_sign=%s calculated_sign=%s",
        extract_callback_value(payload, "store_id"),
        extract_callback_value(payload, "transaction_id"),
        _callback_invoice_for_sign(payload),
        settings.ATMOS_SIGN_ALGORITHM,
        expected_sign,
        calculated,
    )
    return False


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
    after_order_paid(order)
    return True


@transaction.atomic
def process_atmos_callback(payload):
    """
    Atmos Callback API (docs.atmos.uz): validate invoice before payment.
    Response must be {"status": 1, "message": "Успешно"} to allow payment.
    """
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except json.JSONDecodeError:
            payload = {}
    if not isinstance(payload, dict):
        payload = {}

    ok_message = _atmos_callback_ok_message()
    logger.info(
        "Atmos callback: store_id=%s transaction_id=%s account=%s amount=%s",
        extract_callback_value(payload, "store_id"),
        extract_callback_value(payload, "transaction_id"),
        _callback_invoice_for_sign(payload),
        extract_callback_value(payload, "amount"),
    )

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
        logger.warning("Atmos callback rejected: invalid signature")
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
            "message": ok_message,
            "http_status": 200,
            "order": order,
        }

    if order.status not in (
        AtmosOrder.Status.CREATED,
        AtmosOrder.Status.PENDING,
        AtmosOrder.Status.FAILED,
    ):
        logger.warning(
            "Atmos callback rejected: order %s status=%s",
            order.merchant_order_id,
            order.status,
        )
        return {
            "ok": False,
            "atmos_status": 0,
            "message": "Invoice not available",
            "http_status": 200,
        }

    update_fields = ["response_payload", "updated_at"]
    callback_response = {"status": 1, "message": ok_message}
    _append_atmos_trace(
        order,
        step="callback (Atmos -> merchant)",
        request=payload,
        response=callback_response,
    )
    if transaction_id and str(order.atmos_transaction_id) != str(transaction_id):
        order.atmos_transaction_id = str(transaction_id)
        update_fields.append("atmos_transaction_id")
    if order.status == AtmosOrder.Status.CREATED:
        order.status = AtmosOrder.Status.PENDING
        update_fields.append("status")
    elif order.status == AtmosOrder.Status.FAILED:
        order.status = AtmosOrder.Status.PENDING
        update_fields.append("status")
    order.save(update_fields=update_fields)

    logger.info(
        "Atmos callback validated order=%s transaction_id=%s",
        order.merchant_order_id,
        transaction_id,
    )
    return {
        "ok": True,
        "atmos_status": 1,
        "message": ok_message,
        "http_status": 200,
        "order": order,
    }


def cleanup_stale_atmos_orders(*, days=None, all_unpaid=False, dry_run=False):
    """Remove unpaid Atmos orders (and their transactions) to keep the admin tidy.

    Paid orders are never deleted. By default only orders older than
    ``ATMOS_STALE_ORDER_RETENTION_DAYS`` are removed.
    """
    from datetime import timedelta

    retention_days = (
        settings.ATMOS_STALE_ORDER_RETENTION_DAYS if days is None else days
    )
    unpaid_statuses = (
        AtmosOrder.Status.CREATED,
        AtmosOrder.Status.PENDING,
        AtmosOrder.Status.FAILED,
        AtmosOrder.Status.CANCELED,
        AtmosOrder.Status.EXPIRED,
    )
    qs = AtmosOrder.objects.filter(status__in=unpaid_statuses)
    if not all_unpaid:
        cutoff = timezone.now() - timedelta(days=retention_days)
        qs = qs.filter(created_at__lt=cutoff)

    order_count = qs.count()
    if dry_run:
        return {
            "orders": order_count,
            "transactions": AtmosTransaction.objects.filter(order__in=qs).count(),
            "dry_run": True,
        }

    deleted_total, breakdown = qs.delete()
    return {
        "orders": breakdown.get("users.AtmosOrder", 0),
        "transactions": breakdown.get("users.AtmosTransaction", 0),
        "deleted_total": deleted_total,
        "dry_run": False,
    }


def cleanup_expired_offer_messages(*, ttl_seconds=None, dry_run=False):
    """Delete subscription catalog Telegram messages that were not paid in time."""
    from datetime import timedelta

    from .notifications import clear_offer_telegram_messages

    ttl = settings.OFFER_MESSAGE_TTL_SECONDS if ttl_seconds is None else ttl_seconds
    cutoff = timezone.now() - timedelta(seconds=ttl)
    users = TelegramUser.objects.filter(
        offer_message_id__isnull=False,
        offer_chat_id__isnull=False,
        offer_sent_at__isnull=False,
        offer_sent_at__lt=cutoff,
    )
    total = users.count()
    if dry_run:
        return {"users": total, "dry_run": True}

    cleared = 0
    for user in users.iterator():
        if clear_offer_telegram_messages(user):
            cleared += 1
    return {"users": total, "cleared": cleared, "dry_run": False}


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
