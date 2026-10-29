from datetime import timedelta
from unittest.mock import patch

from cryptography.fernet import Fernet
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from users.card_checkout import bind_checkout_card, verify_and_pay
from users.models import ClickCardCheckout, ClickOrder, ClickRenewal, SubscriptionPlan, TelegramUser
from users.recurring import RenewalError, cipher
from users.services import after_order_paid, cancel_subscription


@override_settings(CLICK_RENEWALS_ENABLED=True, CLICK_TOKEN_ENCRYPTION_KEY=Fernet.generate_key().decode(),
                   CLICK_MERCHANT_USER_ID="1", CLICK_SERVICE_ID="2", CLICK_MERCHANT_ID="3",
                   CLICK_SECRET_KEY="secret", CLICK_RETURN_URL="https://example.com/return/",
                   BOT_TOKEN="", BACKEND_PUBLIC_URL="https://example.com")
@patch("users.services._notify_payment_success_safe")
class CardCheckoutTests(TestCase):
    def setUp(self):
        self.user = TelegramUser.objects.create(telegram_id=777)
        self.plan = SubscriptionPlan.objects.create(name="Monthly", price=30000, duration=1, period="month")
        self.order = ClickOrder.create_for_plan(self.user, self.plan)

    def bound(self, order=None):
        order = order or self.order
        return ClickCardCheckout.objects.create(
            order=order, consent_at=timezone.now(), period=self.plan.period, duration=self.plan.duration,
            token_encrypted=cipher().encrypt(b"private-card-token").decode(),
        )

    @patch("users.card_checkout.merchant_request")
    def test_card_sms_payment_and_enrollment_in_one_flow(self, api, notify):
        api.side_effect = [{"error_code": 0, "card_token": "private-card-token"},
                           {"error_code": 0}, {"error_code": 0, "payment_id": 100}]
        client = Client(enforce_csrf_checks=True)
        url = reverse("click-card-checkout", args=[self.order.order_id])
        page = client.get(url)
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, '<input type="hidden" name="consent" value="true">', html=True)
        self.assertNotContains(page, 'type="checkbox"')
        csrf = client.cookies["csrftoken"].value
        response = client.post(url, {"action": "bind", "card_number": "8600000000000000",
                                     "expiry": "1228", "consent": "true"}, HTTP_X_CSRFTOKEN=csrf)
        self.assertEqual(response.status_code, 302)
        self.assertFalse(ClickRenewal.objects.exists())
        self.assertNotContains(client.get(url), "private-card-token")
        response = client.post(url, {"action": "verify", "sms_code": "12345"}, HTTP_X_CSRFTOKEN=csrf)
        self.assertEqual(response.status_code, 302)
        self.order.refresh_from_db()
        self.assertTrue(self.order.is_paid)
        renewal = ClickRenewal.objects.get(user=self.user)
        self.assertTrue(renewal.enabled)
        self.assertEqual(cipher().decrypt(renewal.token_encrypted.encode()), b"private-card-token")
        self.assertEqual(renewal.next_charge_at, self.order.premium_subscription.expires_at)
        self.assertEqual(ClickCardCheckout.objects.get().token_encrypted, "")
        response = client.get(url)
        self.assertContains(response, "To'lov tasdiqlandi")
        self.assertNotContains(response, "private-card-token")
        self.assertEqual(api.call_count, 3)
        payment_path, payment_body = api.call_args.args
        self.assertEqual(payment_path, "card_token/payment")
        self.assertEqual(payment_body["transaction_parameter"], self.order.merchant_order_id)
        self.assertNotIn("merchant_trans_id", payment_body)
        # Reloading and resending the confirmation must not issue another debit.
        self.assertEqual(verify_and_pay(self.order, "12345"), "paid")
        self.assertEqual(api.call_count, 3)

    @patch("users.card_checkout.merchant_request")
    def test_csrf_and_consent_are_required(self, api, notify):
        url = reverse("click-card-checkout", args=[self.order.order_id])
        self.assertEqual(Client(enforce_csrf_checks=True).post(url, {}).status_code, 403)
        with self.assertRaises(RenewalError):
            bind_checkout_card(self.order, "8600000000000000", "1228", False)
        api.assert_not_called()

    @patch("users.card_checkout.merchant_request", return_value={"error_code": -1})
    def test_invalid_sms_never_charges_or_enrolls(self, api, notify):
        self.bound()
        for _ in range(6):
            with self.assertRaises(RenewalError):
                verify_and_pay(self.order, "12345")
        self.assertEqual(api.call_count, 5)
        self.assertFalse(ClickRenewal.objects.exists())
        self.order.refresh_from_db()
        self.assertFalse(self.order.is_paid)

    @patch("users.card_checkout.merchant_request")
    def test_debit_timeout_cannot_repeat(self, api, notify):
        self.bound()
        api.side_effect = [{"error_code": 0}, RenewalError("timeout")]
        self.assertEqual(verify_and_pay(self.order, "12345"), "uncertain")
        self.assertEqual(verify_and_pay(self.order, "12345"), "uncertain")
        self.assertEqual(api.call_count, 2)
        self.assertFalse(ClickRenewal.objects.exists())
        url = reverse("click-card-checkout", args=[self.order.order_id])
        self.assertContains(self.client.get(url), "Qayta to'lov qilmang")

    @patch("users.card_checkout.merchant_request")
    def test_decline_does_not_enable_renewal(self, api, notify):
        self.bound()
        api.side_effect = [{"error_code": 0}, {"error_code": -42, "error_note": "private details", "card_token": "secret"}]
        self.assertEqual(verify_and_pay(self.order, "12345"), "failed")
        self.assertEqual(verify_and_pay(self.order, "12345"), "failed")
        self.assertEqual(api.call_count, 2)
        self.assertFalse(ClickRenewal.objects.exists())

        self.order.refresh_from_db()
        self.assertEqual(self.order.response_payload["merchant_error_code"], "-42")
        self.assertNotIn("secret", str(self.order.response_payload))
        self.assertNotIn("private details", str(self.order.response_payload))
        url = reverse("click-card-checkout", args=[self.order.order_id])
        self.assertContains(self.client.get(url), "Click xato kodi: -42")

    def test_late_callback_enrolls_only_once(self, notify):
        checkout = self.bound()
        checkout.verified = True
        checkout.state = "uncertain"
        checkout.save()
        self.order.mark_as_paid()
        after_order_paid(self.order)
        self.assertTrue(ClickRenewal.objects.get().enabled)
        cancel_subscription(self.user)
        after_order_paid(self.order)
        self.assertFalse(ClickRenewal.objects.get().enabled)

    @patch("users.card_checkout.merchant_request")
    def test_cancellation_during_first_debit_is_respected(self, api, notify):
        self.bound()
        def respond(path, payload):
            if path == "card_token/payment":
                cancel_subscription(self.user)
                return {"error_code": 0, "payment_id": 100}
            return {"error_code": 0}
        api.side_effect = respond
        self.assertEqual(verify_and_pay(self.order, "12345"), "paid")
        self.assertFalse(ClickRenewal.objects.exists())

    @patch("users.card_checkout.merchant_request")
    def test_pending_other_order_blocks_another_debit(self, api, notify):
        old = self.bound()
        old.state = "uncertain"
        old.save()
        second = ClickOrder.create_for_plan(self.user, self.plan)
        self.bound(second)
        with self.assertRaises(RenewalError):
            verify_and_pay(second, "12345")
        api.assert_not_called()

    @patch("users.card_checkout.merchant_request")
    def test_tariff_change_before_verification_stops_payment(self, api, notify):
        self.bound()
        self.plan.price += 1000
        self.plan.save()
        with self.assertRaises(RenewalError):
            verify_and_pay(self.order, "12345")
        api.assert_not_called()

    def test_bot_checkout_uses_integrated_card_form(self, notify):
        url = reverse("click-order-checkout", args=[self.order.order_id])
        response = self.client.get(url)
        self.assertRedirects(response, reverse("click-card-checkout", args=[self.order.order_id]))

    @patch("users.card_checkout.merchant_request")
    def test_expired_sms_does_not_charge(self, api, notify):
        checkout = self.bound()
        checkout.consent_at = timezone.now() - timedelta(minutes=11)
        checkout.save()
        with self.assertRaises(RenewalError):
            verify_and_pay(self.order, "12345")
        api.assert_not_called()

    @patch("users.card_checkout.merchant_request", return_value={"error_code": 0, "card_token": "private-token"})
    def test_https_form_origin_is_preserved_and_csrf_stays_enforced(self, api, notify):
        client = Client(enforce_csrf_checks=True)
        url = reverse("click-card-checkout", args=[self.order.order_id])
        page = client.get(url, secure=True)
        # no-referrer turns a browser's navigation-mode form POST Origin into
        # null; same-origin keeps it and also avoids leaking order URLs off-site.
        self.assertContains(page, '<meta name="referrer" content="same-origin">')
        csrf = client.cookies["csrftoken"].value
        data = {"action": "bind", "card_number": "8600000000000000", "expiry": "1228", "consent": "on"}
        for origin in ("null", "https://attacker.example"):
            response = client.post(url, data, secure=True, HTTP_ORIGIN=origin, HTTP_X_CSRFTOKEN=csrf)
            self.assertEqual(response.status_code, 403)
        self.assertEqual(client.post(url, data, secure=True, HTTP_ORIGIN="https://testserver").status_code, 403)
        api.assert_not_called()
        response = client.post(url, data, secure=True, HTTP_ORIGIN="https://testserver", HTTP_X_CSRFTOKEN=csrf)
        self.assertEqual(response.status_code, 302)
        api.assert_called_once()
