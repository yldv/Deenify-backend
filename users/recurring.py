"""Click Merchant API card tokens and durable, at-most-once renewal attempts.

Protocol reference: click-llc/click-integration-php, Payments/BasePayments.php.
Never retry an uncertain debit automatically: it may already have succeeded.
"""
import hashlib
import json
import time
from urllib.request import Request, urlopen

from cryptography.fernet import Fernet
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .models import ClickOrder, ClickRenewal, ClickRenewalAttempt, UserPremiumSubscription


class RenewalError(Exception):
    pass


def available():
    configured = bool(settings.CLICK_RENEWALS_ENABLED and settings.CLICK_TOKEN_ENCRYPTION_KEY
                and settings.CLICK_MERCHANT_USER_ID and settings.CLICK_SECRET_KEY
                and settings.CLICK_SERVICE_ID)
    if configured:
        try:
            cipher()
        except (ValueError, TypeError):
            return False
    return configured


def cipher():
    return Fernet(settings.CLICK_TOKEN_ENCRYPTION_KEY.encode())


def setup_url(order):
    if not available() or not order or not eligible_order(order):
        return ""
    from django.urls import reverse
    from .services import _public_api_base_url
    return _public_api_base_url() + reverse("click-renewal-setup", kwargs={"order_id": order.order_id})


def merchant_request(path, payload):
    if not available():
        raise RenewalError("Avtouzaytirish hozircha mavjud emas.")
    stamp = str(int(time.time()))
    digest = hashlib.sha1((stamp + settings.CLICK_SECRET_KEY).encode()).hexdigest()
    request = Request(
        "https://api.click.uz/v2/merchant/" + path,
        data=json.dumps({"service_id": settings.CLICK_SERVICE_ID, **payload}).encode(),
        headers={"Content-Type": "application/json", "Accept": "application/json",
                 "Auth": f"{settings.CLICK_MERCHANT_USER_ID}:{digest}:{stamp}"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=15) as response:
            result = json.loads(response.read())
        if not isinstance(result, dict) or "error_code" not in result:
            raise ValueError("Invalid merchant response")
        return result
    except Exception:
        # Do not expose request/response bodies, PAN, SMS or card tokens.
        raise RenewalError("Click javobi olinmadi. Keyinroq holatni tekshiring.") from None


def eligible_order(order):
    if (order.currency != "UZS" or order.plan.currency != "UZS"
            or order.amount != order.plan.price or not order.plan.is_active
            or not order.plan.get_duration_delta()):
        return None
    subscription = UserPremiumSubscription.objects.filter(
        user=order.user, is_active=True, source_order=order,
        expires_at__gt=timezone.now(), plan=order.plan,
    ).first()
    return subscription if order.is_paid and not order.user.is_blocked else None


def request_binding(order, card_number, expiry, consent):
    if not consent or not eligible_order(order):
        raise RenewalError("Amaldagi pullik obuna va rozilik kerak.")
    if not card_number.isdigit() or not 16 <= len(card_number) <= 19:
        raise RenewalError("Karta raqamini tekshiring.")
    if len(expiry) != 4 or not expiry.isdigit():
        raise RenewalError("Karta muddati MMYY shaklida bo'lishi kerak.")
    with transaction.atomic():
        # Also serializes concurrent binding attempts for this user.
        type(order.user).objects.select_for_update().get(pk=order.user_id)
        if ClickRenewal.objects.filter(user=order.user, enabled=True).exists():
            raise RenewalError("Avval amaldagi avtouzaytirishni bekor qiling.")
        recent = ClickRenewal.objects.filter(user=order.user).first()
        if recent and recent.consent_at and (timezone.now() - recent.consent_at).total_seconds() < 60:
            raise RenewalError("Yangi SMS uchun 60 soniya kuting.")
        result = merchant_request("card_token/request", {
            "card_number": card_number, "expire_date": expiry, "temporary": 0,
        })
        if str(result.get("error_code")) != "0" or not result.get("card_token"):
            raise RenewalError("Kartani bog'lab bo'lmadi. Karta ma'lumotlarini tekshiring.")
        renewal, _ = ClickRenewal.objects.update_or_create(user=order.user, defaults={
            "plan": order.plan, "amount": order.amount,
            "period": order.plan.period, "duration": order.plan.duration,
            "token_encrypted": cipher().encrypt(str(result["card_token"]).encode()).decode(),
            "enabled": False, "verified": False, "consent_at": timezone.now(),
            "verify_attempts": 0,
            "next_charge_at": None,
        })
        return renewal


def verify_binding(order, sms_code):
    if not sms_code.isdigit() or not 4 <= len(sms_code) <= 8:
        raise RenewalError("SMS kodini tekshiring.")
    with transaction.atomic():
        type(order.user).objects.select_for_update().get(pk=order.user_id)
        renewal = ClickRenewal.objects.select_for_update().filter(user=order.user).first()
        subscription = eligible_order(order)
        if (not renewal or not subscription or renewal.plan_id != order.plan_id
                or renewal.verified or renewal.verify_attempts >= 5 or not renewal.consent_at
                or not renewal.token_encrypted
                or (timezone.now() - renewal.consent_at).total_seconds() > 600):
            raise RenewalError("Kartani qaytadan bog'lang.")
        renewal.verify_attempts += 1
        try:
            result = merchant_request("card_token/verify", {
                "card_token": cipher().decrypt(renewal.token_encrypted.encode()).decode(),
                "sms_code": sms_code,
            })
            success = str(result.get("error_code")) == "0"
        except RenewalError:
            success = False
        if success:
            renewal.verified = renewal.enabled = True
            renewal.next_charge_at = subscription.expires_at
        renewal.save()
    if not success:
        raise RenewalError("SMS kodi tasdiqlanmadi.")


def sync_renewal(order):
    """Move the next charge after a purchase, referral extension or renewal."""
    subscription = UserPremiumSubscription.objects.filter(source_order=order, is_active=True).first()
    if not subscription:
        return
    ClickRenewalAttempt.objects.filter(order=order).update(state="paid")
    for renewal in ClickRenewal.objects.filter(user=order.user, enabled=True):
        if (renewal.plan_id != order.plan_id or renewal.amount != order.amount or not subscription.expires_at
                or renewal.period != order.plan.period or renewal.duration != order.plan.duration):
            updates = {"enabled": False}
        else:
            updates = {"next_charge_at": subscription.expires_at}
        ClickRenewal.objects.filter(pk=renewal.pk, enabled=True).update(**updates, updated_at=timezone.now())


def charge_due(renewal_id):
    if not available():
        return "disabled"
    with transaction.atomic():
        renewal = ClickRenewal.objects.select_for_update().select_related("user", "plan").get(pk=renewal_id)
        if (not renewal.enabled or not renewal.verified or renewal.user.is_blocked
                or not renewal.next_charge_at or renewal.next_charge_at > timezone.now()):
            return "skipped"
        if (not renewal.plan.is_active or renewal.plan.currency != "UZS"
                or renewal.plan.price != renewal.amount or not renewal.plan.get_duration_delta()):
            renewal.enabled = False
            renewal.save(update_fields=("enabled", "updated_at"))
            return "disabled"
        if renewal.plan.period != renewal.period or renewal.plan.duration != renewal.duration:
            ClickRenewal.objects.filter(pk=renewal.pk).update(enabled=False)
            return "disabled"
        # Referral/manual extensions may postpone the next debit.
        coverage = UserPremiumSubscription.objects.filter(user=renewal.user, is_active=True).order_by("-expires_at").first()
        if coverage and (coverage.expires_at is None or coverage.expires_at > timezone.now()):
            renewal.next_charge_at = coverage.expires_at
            if coverage.expires_at is None:
                renewal.enabled = False
            renewal.save()
            return "postponed"
        if ClickRenewalAttempt.objects.filter(renewal=renewal, due_at=renewal.next_charge_at).exists():
            return "already_attempted"
        order = ClickOrder.create_for_plan(renewal.user, renewal.plan)
        attempt = ClickRenewalAttempt.objects.create(renewal=renewal, due_at=renewal.next_charge_at, order=order)
        order.status = ClickOrder.Status.PENDING
        order.save(update_fields=("status", "updated_at"))
        token = cipher().decrypt(renewal.token_encrypted.encode()).decode()
    # Persist the attempt before sending money requests. A crash/timeout must
    # never cause the scheduler to submit the debit again.
    try:
        result = merchant_request("card_token/payment", {
            "card_token": token, "amount": float(order.amount),
            "merchant_trans_id": order.merchant_order_id,
        })
    except RenewalError:
        ClickRenewalAttempt.objects.filter(pk=attempt.pk, state="processing").update(state="uncertain")
        attempt.refresh_from_db()
        return attempt.state
    if str(result.get("error_code")) == "0" and result.get("payment_id"):
        order.mark_as_paid(click_trans_id=str(result["payment_id"]),
                           payload={"merchant_payment_id": str(result["payment_id"])})
        from .services import after_order_paid
        after_order_paid(order)
        ClickRenewalAttempt.objects.filter(pk=attempt.pk).update(state="paid")
        return "paid"
    # A malformed success is uncertain, not a safe reason for a second debit.
    if str(result.get("error_code")) == "0":
        ClickRenewalAttempt.objects.filter(pk=attempt.pk, state="processing").update(state="uncertain")
        attempt.refresh_from_db()
        return attempt.state
    with transaction.atomic():
        order = ClickOrder.objects.select_for_update().get(pk=order.pk)
        if order.is_paid:  # A SHOP callback may have confirmed it concurrently.
            ClickRenewalAttempt.objects.filter(pk=attempt.pk).update(state="paid")
            return "paid"
        ClickRenewalAttempt.objects.filter(pk=attempt.pk).update(state="failed")
        ClickOrder.objects.filter(pk=order.pk).update(status=ClickOrder.Status.FAILED)
        ClickRenewal.objects.filter(pk=renewal_id).update(enabled=False)
    from .notifications import send_telegram_message
    from bot.texts import get_text
    send_telegram_message(chat_id=renewal.user.telegram_id,
                          text=get_text(renewal.user.get_content_language(), "auto_renew_failed"))
    return "failed"
