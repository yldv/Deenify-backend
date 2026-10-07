import hashlib
from unittest.mock import patch

from django.test import SimpleTestCase, TestCase, override_settings

from users.models import ClickOrder, ClickTransaction, SubscriptionPlan, TelegramUser
from users.services import ClickPaymentService, process_click_callback

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
    "CLICK_BOT_URL": "https://t.me/DeenifyUzBot",
    "CLICK_LANG": "uz",
}


def _sign(payload, *, action="1", secret=SECRET, with_prepare_id=True):
    parts = [
        str(payload["click_trans_id"]),
        str(payload["service_id"]),
        secret,
        str(payload["merchant_trans_id"]),
    ]
    if action == "1" and with_prepare_id:
        parts.append(str(payload["merchant_prepare_id"]))
    parts.extend((str(payload["amount"]), action, str(payload["sign_time"])))
    return hashlib.md5("".join(parts).encode("utf-8")).hexdigest()


def _callback_payload(order, *, click_trans_id="900001", action="0", amount="30000.00"):
    payload = {
        "click_trans_id": click_trans_id,
        "service_id": SERVICE_ID,
        "merchant_id": MERCHANT_ID,
        "merchant_trans_id": order.merchant_order_id,
        "amount": amount,
        "currency": "UZS",
        "error": "0",
        "error_note": "",
        "action": action,
        "sign_time": "20260929-12:00:00",
    }
    if action == "1":
        payload["merchant_prepare_id"] = str(order.pk)
    payload["sign_string"] = _sign(payload, action=action)
    return payload


@override_settings(**CLICK_SETTINGS)
class ClickSignatureTests(SimpleTestCase):
    def setUp(self):
        self.service = ClickPaymentService()

    def _payload(self, action):
        payload = {
            "click_trans_id": "900001",
            "service_id": SERVICE_ID,
            "merchant_trans_id": "order-1",
            "merchant_prepare_id": "42",
            "amount": "30000.00",
            "action": action,
            "sign_time": "20260929-12:00:00",
        }
        payload["sign_string"] = _sign(payload, action=action)
        return payload

    def test_prepare_signature_is_valid(self):
        self.assertTrue(self.service.is_valid_signature(self._payload("0")))

    def test_complete_signature_is_valid(self):
        self.assertTrue(self.service.is_valid_signature(self._payload("1")))

    def test_signature_rejected_with_wrong_secret(self):
        payload = self._payload("1")
        payload["sign_string"] = _sign(payload, action="1", secret="another-secret")
        self.assertFalse(self.service.is_valid_signature(payload))

    def test_complete_signature_requires_prepare_id(self):
        payload = self._payload("1")
        payload["sign_string"] = _sign(payload, action="1", with_prepare_id=False)
        self.assertFalse(self.service.is_valid_signature(payload))

    def test_missing_field_is_rejected(self):
        self.assertFalse(self.service.is_valid_signature({"action": "1"}))

    def test_signature_accepted_from_plain_sign_field(self):
        payload = self._payload("1")
        payload["sign"] = payload.pop("sign_string")
        self.assertTrue(self.service.is_valid_signature(payload))

    def test_signature_accepted_from_query_string_style_sign(self):
        payload = self._payload("0")
        payload["sign"] = payload.pop("sign_string").upper()
        self.assertTrue(self.service.is_valid_signature(payload))


@override_settings(
    **CLICK_SETTINGS,
    BOT_API_SECRET="bot-api-secret",
    BACKEND_PUBLIC_URL="https://api.example.uz",
)
class ClickStartLinkTests(SimpleTestCase):
    def test_roundtrip(self):
        from urllib.parse import parse_qs, urlsplit

        from users.services import build_payment_start_url, verify_payment_start_signature

        url = build_payment_start_url(telegram_id=111, plan_id=7)
        self.assertTrue(url.startswith("https://api.example.uz/api/v1/payments/click/start/?"))
        params = {k: v[0] for k, v in parse_qs(urlsplit(url).query).items()}
        self.assertEqual(params["telegram_id"], "111")
        self.assertEqual(params["plan_id"], "7")
        self.assertTrue(
            verify_payment_start_signature(
                telegram_id=111,
                plan_id=7,
                exp=int(params["exp"]),
                signature=params["sig"],
            )
        )

    def test_tampered_params_are_rejected(self):
        from users.services import verify_payment_start_signature

        self.assertFalse(
            verify_payment_start_signature(
                telegram_id=111, plan_id=999, exp=9999999999, signature="deadbeef"
            )
        )
        self.assertFalse(
            verify_payment_start_signature(telegram_id=111, plan_id=7, exp=9999999999, signature="")
        )
        self.assertFalse(
            verify_payment_start_signature(
                telegram_id=111, plan_id=7, exp=1, signature="deadbeef"
            )
        )

    def test_url_is_empty_without_bot_secret(self):
        from users.services import build_payment_start_url

        with override_settings(BOT_API_SECRET=""):
            self.assertEqual(build_payment_start_url(telegram_id=111, plan_id=7), "")


@override_settings(**CLICK_SETTINGS)
class ClickCheckoutFormTests(SimpleTestCase):
    def test_form_fields(self):
        class FakePlan:
            name = "Oylik obuna"

        class FakeOrder:
            merchant_order_id = "order-1"
            amount = "30000.00"
            currency = "UZS"
            plan = FakePlan()

        fields = ClickPaymentService().checkout_form_fields(FakeOrder())
        self.assertEqual(fields["service_id"], SERVICE_ID)
        self.assertEqual(fields["merchant_id"], MERCHANT_ID)
        self.assertEqual(fields["order_id"], "order-1")
        self.assertEqual(fields["transaction_param"], "order-1")
        self.assertEqual(fields["amount"], "30000.00")
        self.assertEqual(fields["return_url"], CLICK_SETTINGS["CLICK_RETURN_URL"])
        self.assertNotIn("merchant_user_id", fields)

    def test_merchant_user_id_is_sent_when_set(self):
        class FakePlan:
            name = "Oylik obuna"

        class FakeOrder:
            merchant_order_id = "order-1"
            amount = "30000.00"
            currency = "UZS"
            plan = FakePlan()

        with override_settings(CLICK_MERCHANT_USER_ID="user-77"):
            fields = ClickPaymentService().checkout_form_fields(FakeOrder())
        self.assertEqual(fields["merchant_user_id"], "user-77")

    def test_missing_config_is_reported(self):
        with override_settings(CLICK_SECRET_KEY=""):
            self.assertIn("CLICK_SECRET_KEY", ClickPaymentService().missing_config_fields())


@override_settings(**CLICK_SETTINGS)
class ClickCallbackTests(TestCase):
    def setUp(self):
        self.user = TelegramUser.objects.create(telegram_id=111, language="uz")
        self.plan = SubscriptionPlan.objects.create(
            name="Oylik obuna",
            price="30000.00",
            duration=1,
            period="month",
        )
        self.order = ClickOrder.objects.create(
            user=self.user,
            plan=self.plan,
            amount=self.plan.price,
            currency="UZS",
            status=ClickOrder.Status.PENDING,
        )

    def test_wrong_service_id(self):
        payload = _callback_payload(self.order)
        payload["service_id"] = "999999"
        payload["sign_string"] = _sign(payload, action="0")
        self.assertEqual(process_click_callback(payload)["error"], -8)

    @patch("users.notifications.notify_payment_success")
    def test_shop_callbacks_without_merchant_id(self, _notify):
        prepare_payload = _callback_payload(self.order, action="0")
        prepare_payload.pop("merchant_id")
        prepare = process_click_callback(prepare_payload)
        self.assertEqual(prepare["error"], 0)
        self.assertEqual(prepare["merchant_prepare_id"], self.order.pk)

        complete_payload = _callback_payload(self.order, action="1")
        complete_payload.pop("merchant_id")
        complete = process_click_callback(complete_payload)
        self.assertEqual(complete["error"], 0)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, ClickOrder.Status.PAID)

    def test_wrong_explicit_merchant_id(self):
        payload = _callback_payload(self.order)
        payload["merchant_id"] = "wrong-merchant"
        self.assertEqual(process_click_callback(payload)["error"], -7)

    def test_missing_merchant_id_still_requires_valid_signature(self):
        payload = _callback_payload(self.order)
        payload.pop("merchant_id")
        payload["sign_string"] = "0" * 32
        self.assertEqual(process_click_callback(payload)["error"], -1)

    def test_bad_signature(self):
        payload = _callback_payload(self.order)
        payload["sign_string"] = "0" * 32
        self.assertEqual(process_click_callback(payload)["error"], -1)

    def test_unknown_order(self):
        payload = _callback_payload(self.order)
        payload["merchant_trans_id"] = "does-not-exist"
        payload["sign_string"] = _sign(payload, action="0")
        self.assertEqual(process_click_callback(payload)["error"], -5)

    def test_amount_mismatch(self):
        payload = _callback_payload(self.order, amount="1.00")
        self.assertEqual(process_click_callback(payload)["error"], -2)

    @patch("users.notifications.notify_payment_success")
    def test_prepare_then_complete_activates_premium(self, _notify):
        prepare = process_click_callback(_callback_payload(self.order, action="0"))
        self.assertEqual(prepare["error"], 0)
        self.assertEqual(prepare["merchant_prepare_id"], self.order.pk)

        complete = process_click_callback(
            _callback_payload(self.order, action="1", click_trans_id="900002")
        )
        self.assertEqual(complete["error"], 0)
        self.assertEqual(complete["merchant_confirm_id"], self.order.pk)

        self.order.refresh_from_db()
        self.assertEqual(self.order.status, ClickOrder.Status.PAID)
        self.assertEqual(self.order.click_trans_id, "900002")
        self.assertTrue(ClickTransaction.objects.filter(order=self.order).exists())
        self.assertTrue(self.user.has_active_premium())

    @patch("users.notifications.notify_payment_success")
    def test_complete_requires_prepare_id_of_this_order(self, _notify):
        payload = _callback_payload(self.order, action="1")
        payload["merchant_prepare_id"] = str(self.order.pk + 999)
        payload["sign_string"] = _sign(payload, action="1")
        self.assertEqual(process_click_callback(payload)["error"], -6)

    @patch("users.notifications.notify_payment_success")
    def test_cancelled_order_is_rejected_on_prepare(self, _notify):
        self.order.status = ClickOrder.Status.FAILED
        self.order.save(update_fields=("status",))
        self.assertEqual(process_click_callback(_callback_payload(self.order))["error"], -9)

    @patch("users.notifications.notify_payment_success")
    def test_complete_is_idempotent(self, _notify):
        process_click_callback(_callback_payload(self.order, action="0"))
        process_click_callback(
            _callback_payload(self.order, action="1", click_trans_id="900003")
        )
        second = process_click_callback(
            _callback_payload(self.order, action="1", click_trans_id="900003")
        )
        self.assertEqual(second["error"], 0)
        self.assertEqual(self.user.premium_subscriptions.count(), 1)


@override_settings(**CLICK_SETTINGS)
class ClickOrderTests(TestCase):
    def setUp(self):
        self.user = TelegramUser.objects.create(telegram_id=222, language="uz")
        self.plan = SubscriptionPlan.objects.create(
            name="Yillik obuna",
            price="300000.00",
            duration=1,
            period="year",
        )

    @patch("users.services.build_order_checkout_url", return_value="https://x/checkout/1/")
    def test_create_order_is_pending_with_checkout_url(self, _url):
        from users.services import create_click_order

        order = create_click_order(user=self.user, plan=self.plan)
        self.assertEqual(order.status, ClickOrder.Status.PENDING)
        self.assertEqual(order.checkout_url, "https://x/checkout/1/")
        self.assertEqual(order.request_payload["form"]["order_id"], order.merchant_order_id)

    def test_create_order_reports_missing_config(self):
        from users.services import create_click_order

        with override_settings(CLICK_SECRET_KEY=""):
            order = create_click_order(user=self.user, plan=self.plan)
        self.assertEqual(order.status, ClickOrder.Status.CREATED)
        self.assertFalse(order.checkout_url)
        self.assertIn("CLICK_SECRET_KEY", order.response_payload["error"])
