import hashlib
import time
from urllib.parse import urlencode

from django.test import TestCase, override_settings
from django.urls import reverse

from users.models import ClickOrder, SubscriptionPlan, TelegramUser
from users.services import build_payment_start_signature

SECRET = "click-secret-key"
SERVICE_ID = "112668"
MERCHANT_ID = "61627"

CLICK_SETTINGS = {
    "CLICK_SERVICE_ID": SERVICE_ID,
    "CLICK_MERCHANT_ID": MERCHANT_ID,
    "CLICK_MERCHANT_USER_ID": "",
    "CLICK_SECRET_KEY": SECRET,
    "CLICK_PAYMENT_URL": "https://my.click.uz/services/pay",
    "CLICK_RETURN_URL": "https://api.example.uz/api/v1/payments/click/return/",
    "CLICK_CALLBACK_URL": "https://api.example.uz/api/v1/payments/click/callback/",
    "CLICK_BOT_URL": "https://t.me/DeenifyUzBot",
    "CLICK_LANG": "uz",
    "BOT_API_SECRET": "bot-api-secret",
    "BACKEND_PUBLIC_URL": "https://api.example.uz",
}


def _callback_payload(order, *, click_trans_id="910001", action="0"):
    payload = {
        "click_trans_id": click_trans_id,
        "service_id": SERVICE_ID,
        "merchant_id": MERCHANT_ID,
        "merchant_trans_id": order.merchant_order_id,
        "amount": str(order.amount),
        "currency": "UZS",
        "error": "0",
        "error_note": "",
        "action": action,
        "sign_time": "20260929-12:00:00",
    }
    parts = [
        payload["click_trans_id"],
        payload["service_id"],
        SECRET,
        payload["merchant_trans_id"],
    ]
    if action == "1":
        payload["merchant_prepare_id"] = str(order.pk)
        parts.append(payload["merchant_prepare_id"])
    parts.extend((payload["amount"], action, payload["sign_time"]))
    payload["sign"] = hashlib.md5("".join(parts).encode("utf-8")).hexdigest()
    return payload


@override_settings(**CLICK_SETTINGS)
class ClickCheckoutPageTests(TestCase):
    def setUp(self):
        self.user = TelegramUser.objects.create(telegram_id=777, language="uz")
        self.plan = SubscriptionPlan.objects.create(
            name="Oylik obuna",
            price="30000.00",
            duration=1,
            period="month",
        )

    def _start_url(self, **kwargs):
        params = {
            "telegram_id": kwargs.get("telegram_id", self.user.telegram_id),
            "plan_id": kwargs.get("plan_id", self.plan.pk),
            "exp": kwargs.get("exp", int(time.time()) + 600),
        }
        params["sig"] = build_payment_start_signature(**params)
        return f"/api/v1/payments/click/start/?{urlencode(params)}"

    def test_start_page_renders_our_own_html_posting_to_click(self):
        response = self.client.get(self._start_url())
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "payments/click_checkout.html")
        body = response.content.decode()
        self.assertIn('action="https://my.click.uz/services/pay"', body)
        self.assertIn('method="post"', body)
        self.assertIn(f'value="{SERVICE_ID}"', body)
        self.assertIn(f'value="{MERCHANT_ID}"', body)
        self.assertIn('name="transaction_param"', body)
        self.assertEqual(ClickOrder.objects.count(), 1)

    def test_start_page_rejects_tampered_link(self):
        url = self._start_url().replace("sig=", "sig=0")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(ClickOrder.objects.count(), 0)

    def test_start_page_rejects_expired_link(self):
        response = self.client.get(
            "/api/v1/payments/click/start/"
            "?telegram_id=777&plan_id={}&exp=1&sig=deadbeef".format(self.plan.pk)
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(ClickOrder.objects.count(), 0)

    def test_start_page_unknown_user(self):
        response = self.client.get(self._start_url(telegram_id=999))
        self.assertEqual(response.status_code, 404)
        self.assertEqual(ClickOrder.objects.count(), 0)

    def test_start_page_blocked_user(self):
        self.user.is_blocked = True
        self.user.save(update_fields=("is_blocked",))
        response = self.client.get(self._start_url())
        self.assertEqual(response.status_code, 403)
        self.assertEqual(ClickOrder.objects.count(), 0)

    def test_start_page_unknown_plan(self):
        response = self.client.get(self._start_url(plan_id=999))
        self.assertEqual(response.status_code, 404)
        self.assertEqual(ClickOrder.objects.count(), 0)

    def test_start_page_unconfigured_click(self):
        with override_settings(CLICK_SECRET_KEY=""):
            response = self.client.get(self._start_url())
        self.assertEqual(response.status_code, 503)
        self.assertIn("CLICK_SECRET_KEY", response.content.decode())

    def test_checkout_url_reopens_same_order(self):
        response = self.client.get(self._start_url())
        order = ClickOrder.objects.get()
        reopened = self.client.get(
            reverse("click-order-checkout", args=[order.order_id])
        )
        self.assertEqual(reopened.status_code, 200)
        self.assertEqual(ClickOrder.objects.count(), 1)
        self.assertTemplateUsed(reopened, "payments/click_checkout.html")

    def test_checkout_url_unknown_order(self):
        response = self.client.get(reverse("click-order-checkout", args=["nope"]))
        self.assertEqual(response.status_code, 404)

    def test_paid_order_checkout_url_shows_return_page(self):
        self.client.get(self._start_url())
        order = ClickOrder.objects.get()
        order.status = ClickOrder.Status.PAID
        order.save(update_fields=("status",))
        response = self.client.get(
            reverse("click-order-checkout", args=[order.order_id])
        )
        self.assertTemplateUsed(response, "payments/click_return.html")

    def test_return_page(self):
        response = self.client.get(reverse("click-return"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "payments/click_return.html")
        self.assertIn("t.me/DeenifyUzBot", response.content.decode())

    def test_callback_endpoint_is_public(self):
        self.client.get(self._start_url())
        order = ClickOrder.objects.get()
        response = self.client.post(
            reverse("click-callback"), _callback_payload(order), content_type="application/json"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["error"], 0)

    def test_callback_endpoint_accepts_form_post(self):
        self.client.get(self._start_url())
        order = ClickOrder.objects.get()
        response = self.client.post(reverse("click-callback"), _callback_payload(order))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["error"], 0)

    def test_checkout_and_callback_url_names(self):
        self.assertEqual(
            reverse("click-callback"),
            "/api/v1/payments/click/callback/",
        )
        self.assertEqual(
            reverse("click-return"),
            "/api/v1/payments/click/return/",
        )
        self.assertEqual(
            reverse("click-payment-start"),
            "/api/v1/payments/click/start/",
        )
