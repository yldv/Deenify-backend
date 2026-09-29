import hashlib
import hmac
import logging
import time
from decimal import Decimal
from secrets import randbelow
from urllib.parse import urlencode

logger = logging.getLogger(__name__)

from django.conf import settings
from django.db import transaction
from django.db.models import Q, Sum
from django.utils import timezone

from core.constants import SUPPORTED_LANGUAGES
from tests.models import UserAnsweredTest
from tests.quiz_services import get_quiz_progress

from .models import (
    ClickOrder,
    ClickTransaction,
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
    if user.click_orders.filter(status=ClickOrder.Status.PAID).exists():
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
        user.click_orders.filter(
            status__in=(ClickOrder.Status.CREATED, ClickOrder.Status.PENDING),
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


# ---------------------------------------------------------------------------
# Click: payment form + Merchant API callback
# ---------------------------------------------------------------------------


def generate_merchant_order_id(user):
    timestamp = timezone.now().strftime("%Y%m%d%H%M%S%f")
    suffix = f"{randbelow(1_000_000):06d}"
    return f"{timestamp}{user.telegram_id}{suffix}"[:64]


class ClickPaymentService:
    """Click custom HTML-form integration.

    The customer stays on our own checkout page: we render a small HTML form
    that POSTs to Click's payment page (``CLICK_PAYMENT_URL``).  Click then
    calls our Merchant API callback twice (Prepare ``action=0`` and Complete
    ``action=1``) and redirects the browser to ``CLICK_RETURN_URL``.

    Click amounts are in UZS (not tiyins).  The form only carries the order
    reference — the amount is always re-validated server-side in the callback
    before a subscription is enabled.
    """

    def is_configured(self):
        return not self.missing_config_fields()

    def missing_config_fields(self):
        return [
            name
            for name, value in (
                ("CLICK_SERVICE_ID", settings.CLICK_SERVICE_ID),
                ("CLICK_MERCHANT_ID", settings.CLICK_MERCHANT_ID),
                ("CLICK_SECRET_KEY", settings.CLICK_SECRET_KEY),
                ("CLICK_RETURN_URL", settings.CLICK_RETURN_URL),
            )
            if not value
        ]

    @staticmethod
    def amount_string(amount) -> str:
        return format(Decimal(str(amount)).quantize(Decimal("0.01")), "f")

    def checkout_form_fields(self, order) -> dict:
        """Hidden inputs of the HTML form that opens Click's payment page."""
        self._require_config()
        plan_name = (order.plan.name if order.plan else "Deenify Premium")[:200]
        fields = {
            "service_id": settings.CLICK_SERVICE_ID,
            "merchant_id": settings.CLICK_MERCHANT_ID,
            "order_id": order.merchant_order_id,
            "transaction_param": order.merchant_order_id,
            "amount": self.amount_string(order.amount),
            "currency": (order.currency or "UZS").upper(),
            "description": f"Deenify: {plan_name}",
            "lang": settings.CLICK_LANG,
            "return_url": settings.CLICK_RETURN_URL,
        }
        if settings.CLICK_MERCHANT_USER_ID:
            fields["merchant_user_id"] = settings.CLICK_MERCHANT_USER_ID
        return fields

    def _require_config(self):
        missing = self.missing_config_fields()
        if missing:
            raise ValueError(f"Click is not configured: {', '.join(missing)}")

    @staticmethod
    def build_sign_string(payload, secret_key: str) -> str:
        """Click's documented MD5 signature source string.

        Prepare:  click_trans_id + service_id + secret + merchant_trans_id
                  + amount + action + sign_time
        Complete: ... + merchant_prepare_id before amount.
        """
        action = str(payload["action"])
        parts = [
            str(payload["click_trans_id"]),
            str(payload["service_id"]),
            secret_key,
            str(payload["merchant_trans_id"]),
        ]
        if action == "1":
            parts.append(str(payload["merchant_prepare_id"]))
        parts.extend((str(payload["amount"]), action, str(payload["sign_time"])))
        return "".join(parts)

    def is_valid_signature(self, payload) -> bool:
        try:
            expected = hashlib.md5(
                self.build_sign_string(payload, settings.CLICK_SECRET_KEY).encode("utf-8")
            ).hexdigest()
        except (KeyError, TypeError):
            return False
        received = payload.get("sign_string") or payload.get("sign") or ""
        return hmac.compare_digest(expected, str(received).strip().lower())


def create_click_order(*, user, plan) -> ClickOrder:
    """Create the local order and prepare the data for our checkout page."""
    order = ClickOrder.objects.create(
        user=user,
        plan=plan,
        merchant_order_id=generate_merchant_order_id(user),
        amount=plan.price,
        currency=plan.currency,
        status=ClickOrder.Status.CREATED,
    )
    try:
        service = ClickPaymentService()
        fields = service.checkout_form_fields(order)
    except ValueError as exc:
        order.response_payload = {"error": str(exc)}
    else:
        order.checkout_url = build_order_checkout_url(order)
        order.request_payload = {"form": fields}
        order.response_payload = {"form_target": settings.CLICK_PAYMENT_URL}
        order.status = ClickOrder.Status.PENDING
    order.save(
        update_fields=(
            "checkout_url",
            "request_payload",
            "response_payload",
            "status",
            "updated_at",
        )
    )
    return order


def _public_api_base_url() -> str:
    public_base = (getattr(settings, "BACKEND_PUBLIC_URL", "") or "").strip().rstrip("/")
    if public_base:
        return public_base
    return ""


PAYMENT_START_TOKEN_TTL = 3600


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
    return f"{base}/api/v1/payments/click/start/?{query}"


def build_order_checkout_url(order) -> str:
    """Public URL of the checkout page for one specific order."""
    base = _public_api_base_url()
    if not base or not order.order_id:
        return ""
    return f"{base}/api/v1/payments/click/checkout/{order.order_id}/"


def build_bot_payment_url(order) -> str:
    """Link the bot puts in a button: always our own checkout page, never Click's."""
    if order.checkout_url:
        return order.checkout_url.strip()
    return build_order_checkout_url(order)


def click_checkout_context(order) -> dict:
    """Everything the checkout template needs to render the Click form."""
    plan = order.plan
    service = ClickPaymentService()
    return {
        "order": order,
        "plan_name": plan.name if plan else "Deenify Premium",
        "plan_description": (plan.description if plan else "") or "",
        "amount": service.amount_string(order.amount),
        "amount_display": f"{order.amount:,.2f}".replace(",", " "),
        "currency": order.currency,
        "form_action": settings.CLICK_PAYMENT_URL,
        "form_fields": service.checkout_form_fields(order),
        "bot_url": settings.CLICK_BOT_URL or "https://t.me/DeenifyUzBot",
    }


def process_click_callback(payload):
    """Handle Click's Merchant API calls: Prepare (action=0) and Complete (action=1)."""
    service = ClickPaymentService()
    base = {
        "click_trans_id": str(payload.get("click_trans_id", "")),
        "merchant_trans_id": str(payload.get("merchant_trans_id", "")),
    }

    if str(payload.get("service_id", "")) != str(settings.CLICK_SERVICE_ID):
        return {**base, "error": -8, "error_note": "Error in service_id"}
    if settings.CLICK_MERCHANT_ID and str(payload.get("merchant_id", "")) != str(
        settings.CLICK_MERCHANT_ID
    ):
        return {**base, "error": -7, "error_note": "Error in merchant_id"}
    if not service.is_valid_signature(payload):
        logger.warning("Click callback signature check failed %s", base)
        return {**base, "error": -1, "error_note": "SIGN CHECK FAILED!"}

    order = (
        ClickOrder.objects.select_related("plan", "user")
        .filter(merchant_order_id=base["merchant_trans_id"])
        .first()
    )
    if not order:
        return {**base, "error": -5, "error_note": "User does not exist"}
    if service.amount_string(payload.get("amount", "0")) != service.amount_string(order.amount):
        logger.warning(
            "Click callback amount mismatch order=%s callback=%s expected=%s",
            order.merchant_order_id,
            payload.get("amount"),
            order.amount,
        )
        return {**base, "error": -2, "error_note": "Incorrect parameter amount"}

    action = str(payload.get("action", ""))
    if action == "0":  # Prepare: validate the order, do not grant premium yet.
        if order.status not in (
            ClickOrder.Status.CREATED,
            ClickOrder.Status.PENDING,
            ClickOrder.Status.PAID,
        ):
            return {**base, "error": -9, "error_note": "Transaction cancelled"}
        return {**base, "merchant_prepare_id": order.pk, "error": 0, "error_note": "Success"}

    if action == "1":  # Complete: Click has charged the customer.
        if str(payload.get("merchant_prepare_id", "")) != str(order.pk):
            return {**base, "error": -6, "error_note": "Transaction does not exist"}
        if str(payload.get("error", "0")) != "0":
            _mark_order_failed(order, {"click_callback": dict(payload)})
            return {
                **base,
                "merchant_confirm_id": order.pk,
                "error": -9,
                "error_note": "Transaction cancelled",
            }
        if _click_trans_already_used(order, base["click_trans_id"]):
            return {
                **base,
                "merchant_confirm_id": order.pk,
                "error": -9,
                "error_note": "Transaction cancelled",
            }

        _record_click_transaction(order, base["click_trans_id"], dict(payload))
        order.mark_as_paid(click_trans_id=base["click_trans_id"], payload={"click_callback": dict(payload)})
        after_order_paid(order)
        return {**base, "merchant_confirm_id": order.pk, "error": 0, "error_note": "Success"}

    return {**base, "error": -3, "error_note": "Action not found"}


def _click_trans_already_used(order, click_trans_id) -> bool:
    """A Click transaction may confirm exactly one order."""
    if not click_trans_id:
        return False
    return (
        ClickOrder.objects.filter(click_trans_id=click_trans_id, status=ClickOrder.Status.PAID)
        .exclude(pk=order.pk)
        .exists()
    )


def _record_click_transaction(order, click_trans_id, payload):
    if not click_trans_id:
        return
    ClickTransaction.objects.update_or_create(
        order=order,
        transaction_id=click_trans_id,
        defaults={
            "status": ClickTransaction.Status.SUCCESS,
            "amount": order.amount,
            "currency": order.currency,
            "provider_payload": payload,
            "performed_at": timezone.now(),
        },
    )


def _mark_order_failed(order, payload):
    existing = order.response_payload if isinstance(order.response_payload, dict) else {}
    order.status = ClickOrder.Status.FAILED
    if payload:
        existing["last_error_response"] = payload
    order.response_payload = existing
    order.save(update_fields=("status", "response_payload", "updated_at"))


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


def cancel_subscription(user) -> dict:
    """End the current premium period.

    Click charges once per purchase, so there is nothing to unbind or refund.
    Cancelling disables the active subscription right away: the user no longer
    gets premium features, and no automatic renewal exists to stop.
    """
    subscription = get_active_premium_subscription(user)
    if not subscription:
        return {"ok": True, "had_premium": False, "expires_at": None}
    expires_at = subscription.expires_at
    UserPremiumSubscription.objects.filter(pk=subscription.pk).update(
        is_active=False, updated_at=timezone.now()
    )
    return {"ok": True, "had_premium": True, "expires_at": expires_at}


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
            source=source,
        )


def grant_referral_reward(order):
    """Reward the inviter when the invited user makes their FIRST successful payment."""
    user = order.user
    referrer_id = getattr(user, "referred_by_id", None)
    if not referrer_id or user.referral_rewarded:
        return None

    days = (
        settings.CLICK_REFERRAL_BONUS_DAYS_YEARLY
        if _plan_is_yearly(order.plan)
        else settings.CLICK_REFERRAL_BONUS_DAYS_MONTHLY
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
    monthly = settings.CLICK_REFERRAL_BONUS_DAYS_MONTHLY
    yearly = settings.CLICK_REFERRAL_BONUS_DAYS_YEARLY
    return {
        "invited_count": invited_qs.count(),
        "paid_count": paid_count,
        "reward_subscriptions": bonus_days,
        "bonus_days_monthly": monthly,
        "bonus_days_yearly": yearly,
    }


# ---------------------------------------------------------------------------
# Housekeeping
# ---------------------------------------------------------------------------


def cleanup_stale_click_orders(*, days=None, all_unpaid=False, dry_run=False):
    """Remove unpaid Click orders (and their transactions) to keep the admin tidy.

    Paid orders are never deleted. By default only orders older than
    ``CLICK_STALE_ORDER_RETENTION_DAYS`` are removed.
    """
    from datetime import timedelta

    retention_days = (
        settings.CLICK_STALE_ORDER_RETENTION_DAYS if days is None else days
    )
    unpaid_statuses = (
        ClickOrder.Status.CREATED,
        ClickOrder.Status.PENDING,
        ClickOrder.Status.FAILED,
        ClickOrder.Status.CANCELED,
        ClickOrder.Status.EXPIRED,
    )
    qs = ClickOrder.objects.filter(status__in=unpaid_statuses)
    if not all_unpaid:
        cutoff = timezone.now() - timedelta(days=retention_days)
        qs = qs.filter(created_at__lt=cutoff)

    order_count = qs.count()
    if dry_run:
        return {
            "orders": order_count,
            "transactions": ClickTransaction.objects.filter(order__in=qs).count(),
            "dry_run": True,
        }

    deleted_total, breakdown = qs.delete()
    return {
        "orders": breakdown.get("users.ClickOrder", 0),
        "transactions": breakdown.get("users.ClickTransaction", 0),
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
    paid_orders = ClickOrder.objects.filter(status=ClickOrder.Status.PAID)
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
        "total_orders": ClickOrder.objects.count(),
        "paid_orders": paid_orders.count(),
        "failed_orders": ClickOrder.objects.filter(status=ClickOrder.Status.FAILED).count(),
        "total_revenue": total_revenue,
        "today_revenue": today_revenue,
    }


def get_active_plan(plan_id):
    return SubscriptionPlan.objects.filter(id=plan_id, is_active=True).first()
