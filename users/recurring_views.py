from django import forms
from django.shortcuts import get_object_or_404, render, redirect
from django.urls import reverse
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.debug import sensitive_post_parameters

from .models import ClickCardCheckout, ClickOrder, ClickRenewal
from .recurring import RenewalError, available, eligible_order, request_binding, verify_binding


class BindForm(forms.Form):
    card_number = forms.RegexField(r"^[0-9]{16,19}$")
    expiry = forms.RegexField(r"^(0[1-9]|1[0-2])[0-9]{2}$")
    consent = forms.BooleanField()


class VerifyForm(forms.Form):
    sms_code = forms.RegexField(r"^[0-9]{4,8}$")


@method_decorator(never_cache, name="dispatch")
@method_decorator(csrf_protect, name="dispatch")
@method_decorator(sensitive_post_parameters("card_number", "expiry", "sms_code"), name="dispatch")
class ClickRenewalSetupView(View):
    """The opaque checkout order ID is a short-lived enrollment capability."""

    def dispatch(self, request, order_id):
        self.order = get_object_or_404(ClickOrder.objects.select_related("user", "plan"), order_id=order_id)
        if (not available() or not eligible_order(self.order) or not self.order.paid_at
                or (timezone.now() - self.order.paid_at).total_seconds() > 86400):
            return render(request, "payments/click_renewal.html", {"unavailable": True}, status=403)
        return super().dispatch(request, order_id)

    def page(self, request, *, error="", status=200):
        renewal = ClickRenewal.objects.filter(user=self.order.user).first()
        return render(request, "payments/click_renewal.html", {
            "order": self.order, "renewal": renewal, "error": error,
            "verify": bool(renewal and not renewal.verified and renewal.token_encrypted),
        }, status=status)

    def get(self, request, order_id):
        return self.page(request)

    def post(self, request, order_id):
        try:
            action = request.POST.get("action")
            form = VerifyForm(request.POST) if action == "verify" else BindForm(request.POST)
            if not form.is_valid():
                raise RenewalError("Maydonlarni tekshiring va rozilikni tasdiqlang.")
            if action == "verify":
                verify_binding(self.order, **form.cleaned_data)
            else:
                request_binding(self.order, **form.cleaned_data)
        except RenewalError as exc:
            return self.page(request, error=str(exc), status=400)
        return redirect(reverse("click-renewal-setup", kwargs={"order_id": self.order.order_id}))


@method_decorator(never_cache, name="dispatch")
@method_decorator(csrf_protect, name="dispatch")
@method_decorator(sensitive_post_parameters("card_number", "expiry", "sms_code"), name="dispatch")
class ClickCardCheckoutView(View):
    def page(self, request, *, error="", status=200):
        from django.conf import settings
        self.order.refresh_from_db()
        if self.order.is_paid:
            from .recurring import sync_renewal
            sync_renewal(self.order)
        checkout = ClickCardCheckout.objects.filter(order=self.order).first()
        from .recurring import merchant_error_code
        provider_code = (self.order.response_payload or {}).get("merchant_error_code")
        provider_code = merchant_error_code({"error_code": provider_code}) if provider_code is not None else ""
        return render(request, "payments/click_card_checkout.html", {
            "order": self.order, "checkout": checkout, "error": error,
            "provider_code": provider_code,
            "amount_display": format(self.order.amount, ",.2f").rstrip("0").rstrip(".").replace(",", " "),
            "bot_url": settings.CLICK_BOT_URL,
            "verify": bool(checkout and checkout.state == "awaiting_sms"),
            "waiting": bool(checkout and checkout.state in ("processing", "uncertain")),
        }, status=status)

    def dispatch(self, request, order_id):
        from .card_checkout import payable
        self.order = get_object_or_404(ClickOrder.objects.select_related("user", "plan"), order_id=order_id)
        if (not self.order.is_paid and not payable(self.order)
                and not ClickCardCheckout.objects.filter(order=self.order).exists()):
            return self.page(request, error="To'lov hozircha mavjud emas. Botdan yangi havola oling.", status=403)
        return super().dispatch(request, order_id)

    def get(self, request, order_id):
        return self.page(request)

    def post(self, request, order_id):
        from .card_checkout import bind_checkout_card, verify_and_pay
        try:
            action = request.POST.get("action")
            if action not in ("bind", "verify"):
                raise RenewalError("Noto'g'ri amal.")
            form = VerifyForm(request.POST) if action == "verify" else BindForm(request.POST)
            if not form.is_valid():
                raise RenewalError("Maydonlarni tekshiring va rozilikni tasdiqlang.")
            if action == "verify":
                verify_and_pay(self.order, **form.cleaned_data)
            else:
                bind_checkout_card(self.order, **form.cleaned_data)
        except RenewalError as exc:
            return self.page(request, error=str(exc), status=400)
        return redirect(reverse("click-card-checkout", kwargs={"order_id": self.order.order_id}))
