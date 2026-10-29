"""Bind a card and pay the first order in one customer flow."""
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from .models import ClickCardCheckout, ClickOrder, ClickRenewal, TelegramUser
from .recurring import RenewalError, available, cipher, merchant_error_code, merchant_request


def payable(order):
    return (available() and not order.user.is_blocked and order.plan.is_active
            and order.status in (ClickOrder.Status.CREATED, ClickOrder.Status.PENDING)
            and order.currency == order.plan.currency == "UZS"
            and order.amount == order.plan.price and order.amount > 0
            and bool(order.plan.get_duration_delta())
            and order.created_at > timezone.now() - timedelta(hours=24))


def bind_checkout_card(order, card_number, expiry, consent):
    if (not consent or not card_number.isdigit() or not 16 <= len(card_number) <= 19
            or not expiry.isdigit() or len(expiry) != 4 or not 1 <= int(expiry[:2]) <= 12):
        raise RenewalError("Karta ma'lumotlari va rozilikni tekshiring.")
    with transaction.atomic():
        TelegramUser.objects.select_for_update().get(pk=order.user_id)
        order = ClickOrder.objects.select_for_update().select_related("user", "plan").get(pk=order.pk)
        if not payable(order):
            raise RenewalError("Buyurtmani to'lab bo'lmaydi. Botdan yangi havola oling.")
        # Do not start another purchase while an earlier initial debit is unresolved.
        if ClickCardCheckout.objects.filter(order__user_id=order.user_id,
                                           state__in=("processing", "uncertain")).exists():
            raise RenewalError("Oldingi to'lov natijasi kutilmoqda. Qayta to'lov qilmang.")
        current = ClickCardCheckout.objects.filter(order=order).first()
        if current and current.state != "awaiting_sms":
            raise RenewalError("Bu to'lov uchun qayta karta bog'lab bo'lmaydi.")
        latest = ClickCardCheckout.objects.filter(order__user_id=order.user_id).order_by("-consent_at").first()
        if latest and (timezone.now() - latest.consent_at).total_seconds() < 60:
            raise RenewalError("Yangi SMS uchun 60 soniya kuting.")
        result = merchant_request("card_token/request", {
            "card_number": card_number, "expire_date": expiry, "temporary": 0,
        })
        if str(result.get("error_code")) != "0" or not result.get("card_token"):
            raise RenewalError("Kartani bog'lab bo'lmadi. Ma'lumotlarni tekshiring.")
        return ClickCardCheckout.objects.update_or_create(order=order, defaults={
            "token_encrypted": cipher().encrypt(str(result["card_token"]).encode()).decode(),
            "consent_at": timezone.now(), "period": order.plan.period, "duration": order.plan.duration,
            "verify_attempts": 0, "verified": False, "auto_renew_requested": True,
        })[0]


def verify_and_pay(order, sms_code):
    if not sms_code.isdigit() or not 4 <= len(sms_code) <= 8:
        raise RenewalError("SMS kodini tekshiring.")
    with transaction.atomic():
        TelegramUser.objects.select_for_update().get(pk=order.user_id)
        order = ClickOrder.objects.select_for_update().select_related("user", "plan").get(pk=order.pk)
        checkout = ClickCardCheckout.objects.select_for_update().filter(order=order).first()
        if order.is_paid:
            return "paid"
        if checkout and checkout.state != "awaiting_sms":
            return checkout.state
        if ClickCardCheckout.objects.filter(order__user_id=order.user_id,
                                           state__in=("processing", "uncertain")).exclude(order=order).exists():
            raise RenewalError("Oldingi to'lov natijasi kutilmoqda. Qayta to'lov qilmang.")
        if (not payable(order) or not checkout or checkout.verify_attempts >= 5
                or not checkout.auto_renew_requested
                or checkout.period != order.plan.period or checkout.duration != order.plan.duration
                or (timezone.now() - checkout.consent_at).total_seconds() > 600):
            raise RenewalError("To'lov havolasini botdan qaytadan oching.")
        checkout.verify_attempts += 1
        token = cipher().decrypt(checkout.token_encrypted.encode()).decode()
        try:
            result = merchant_request("card_token/verify", {"card_token": token, "sms_code": sms_code})
            verified = str(result.get("error_code")) == "0"
        except RenewalError:
            verified = False
        if verified:
            checkout.verified = True
            checkout.state = "processing"
        checkout.save()
    if not verified:
        raise RenewalError("SMS kodi tasdiqlanmadi.")
    # The processing claim is committed BEFORE submitting the debit. Double
    # clicks, reloads, crashes and uncertain network results cannot repeat it.
    try:
        result = merchant_request("card_token/payment", {
            "card_token": token, "amount": float(order.amount),
            "merchant_trans_id": order.merchant_order_id,
        })
    except RenewalError:
        result = None
    if result and str(result.get("error_code")) == "0" and result.get("payment_id"):
        order.mark_as_paid(click_trans_id=str(result["payment_id"]),
                           payload={"merchant_payment_id": str(result["payment_id"])})
        from .services import after_order_paid
        after_order_paid(order)
        return "paid"
    with transaction.atomic():
        order = ClickOrder.objects.select_for_update().get(pk=order.pk)
        if order.is_paid:
            return "paid"
        state = "uncertain" if result is None or str(result.get("error_code")) == "0" else "failed"
        ClickCardCheckout.objects.filter(pk=checkout.pk, state="processing").update(state=state)
        if state == "failed":
            order.status = ClickOrder.Status.FAILED
            order.response_payload = {**(order.response_payload or {}),
                                      "merchant_error_code": merchant_error_code(result),
                                      "merchant_error_stage": "card_token/payment"}
            order.save(update_fields=("status", "response_payload", "updated_at"))
        return state


def activate_checkout_renewal(order):
    """Install the saved mandate only after the first payment is confirmed.

    Also runs for a late successful SHOP callback after a debit timeout.
    Cancellation during an in-flight payment must not re-enable renewal.
    """
    with transaction.atomic():
        TelegramUser.objects.select_for_update().get(pk=order.user_id)
        checkout = ClickCardCheckout.objects.select_for_update().filter(order=order).first()
        if not checkout or not checkout.verified or checkout.state == "paid":
            return
        paid_order = ClickOrder.objects.get(pk=order.pk)
        if not paid_order.is_paid:
            return
        subscription = getattr(paid_order, "premium_subscription", None)
        if (subscription and subscription.expires_at and checkout.auto_renew_requested
                and checkout.token_encrypted):
            ClickRenewal.objects.update_or_create(user_id=order.user_id, defaults={
                "plan_id": order.plan_id, "amount": paid_order.amount,
                "period": checkout.period, "duration": checkout.duration,
                "token_encrypted": checkout.token_encrypted, "consent_at": checkout.consent_at,
                "enabled": True, "verified": True, "verify_attempts": checkout.verify_attempts,
                "next_charge_at": subscription.expires_at,
            })
        checkout.state = "paid"
        checkout.token_encrypted = ""
        checkout.save(update_fields=("state", "token_encrypted", "updated_at"))
