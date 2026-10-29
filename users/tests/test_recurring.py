from datetime import timedelta
from unittest.mock import patch

from cryptography.fernet import Fernet
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from users.models import ClickOrder, ClickRenewal, ClickRenewalAttempt, SubscriptionPlan, TelegramUser
from users.recurring import RenewalError, charge_due, cipher, request_binding, verify_binding
from users.services import cancel_subscription, cleanup_stale_click_orders


@override_settings(CLICK_RENEWALS_ENABLED=True, CLICK_TOKEN_ENCRYPTION_KEY=Fernet.generate_key().decode(),
                   CLICK_MERCHANT_USER_ID="1", CLICK_SERVICE_ID="2", CLICK_SECRET_KEY="secret",
                   BOT_TOKEN="", BACKEND_PUBLIC_URL="https://example.com")
class RenewalTests(TestCase):
    def setUp(self):
        self.user = TelegramUser.objects.create(telegram_id=555)
        self.plan = SubscriptionPlan.objects.create(name="Monthly", price=30000, duration=1, period="month")
        self.order = ClickOrder.create_for_plan(self.user, self.plan)
        self.subscription = self.order.mark_as_paid()
        self.order.refresh_from_db()

    def renewal(self, due=True):
        when = timezone.now() - timedelta(seconds=10) if due else self.subscription.expires_at
        if due:
            self.user.premium_subscriptions.filter(is_active=True).update(expires_at=when)
            self.subscription.expires_at = when
            self.subscription.save()
        return ClickRenewal.objects.create(
            user=self.user, plan=self.plan, amount=self.plan.price, enabled=True, verified=True,
            period=self.plan.period, duration=self.plan.duration,
            consent_at=timezone.now(), next_charge_at=when,
            token_encrypted=cipher().encrypt(b"token").decode(),
        )

    @patch("users.recurring.merchant_request")
    def test_binding_requires_consent_and_sms(self, api):
        with self.assertRaises(RenewalError):
            request_binding(self.order, "8600000000000000", "1228", False)
        api.assert_not_called()
        api.return_value = {"error_code": 0, "card_token": "private-token"}
        renewal = request_binding(self.order, "8600000000000000", "1228", True)
        self.assertFalse(renewal.enabled)
        self.assertNotIn("private-token", renewal.token_encrypted)
        self.assertEqual(api.call_args.args[1]["temporary"], 0)
        api.return_value = {"error_code": 0}
        verify_binding(self.order, "12345")
        renewal.refresh_from_db()
        self.assertTrue(renewal.enabled)
        self.assertEqual(renewal.next_charge_at, self.subscription.expires_at)

    @patch("users.recurring.merchant_request", return_value={"error_code": -1})
    def test_sms_attempts_are_limited(self, api):
        renewal = self.renewal(due=False)
        renewal.enabled = renewal.verified = False
        renewal.save()
        for _ in range(6):
            with self.assertRaises(RenewalError):
                verify_binding(self.order, "12345")
        self.assertEqual(api.call_count, 5)

    @patch("users.services._notify_payment_success_safe")
    @patch("users.recurring.merchant_request", return_value={"error_code": 0, "payment_id": 123})
    def test_every_finite_tariff_renews_once(self, api, notify):
        for period in ("day", "week", "month", "year"):
            with self.subTest(period=period):
                ClickRenewalAttempt.objects.all().delete()
                ClickRenewal.objects.all().delete()
                self.plan.period = period
                self.plan.save()
                renewal = self.renewal()
                self.assertEqual(charge_due(renewal.pk), "paid")
                renewal.refresh_from_db()
                self.assertGreater(renewal.next_charge_at, timezone.now())
                self.assertEqual(charge_due(renewal.pk), "skipped")
        self.assertEqual(api.call_count, 4)

    @patch("users.recurring.merchant_request", side_effect=RenewalError("timeout"))
    def test_timeout_cannot_double_charge(self, api):
        renewal = self.renewal()
        self.assertEqual(charge_due(renewal.pk), "uncertain")
        self.assertEqual(charge_due(renewal.pk), "already_attempted")
        self.assertEqual(api.call_count, 1)
        self.assertEqual(ClickRenewalAttempt.objects.get().state, "uncertain")

    @patch("users.recurring.merchant_request")
    def test_cancel_preserves_paid_coverage_and_stops_debits(self, api):
        renewal = self.renewal(due=False)
        cancel_subscription(self.user)
        renewal.refresh_from_db()
        self.subscription.refresh_from_db()
        self.assertFalse(renewal.enabled)
        self.assertEqual(renewal.token_encrypted, "")
        self.assertTrue(self.subscription.is_current)
        self.assertEqual(charge_due(renewal.pk), "skipped")
        api.assert_not_called()

    @patch("users.recurring.merchant_request")
    def test_changed_price_does_not_charge(self, api):
        renewal = self.renewal()
        self.plan.price += 1000
        self.plan.save()
        self.assertEqual(charge_due(renewal.pk), "disabled")
        api.assert_not_called()

    @patch("users.recurring.merchant_request")
    def test_referral_extension_postpones_charge(self, api):
        renewal = self.renewal()
        self.subscription.expires_at = timezone.now() + timedelta(days=10)
        self.subscription.save()
        self.assertEqual(charge_due(renewal.pk), "postponed")
        api.assert_not_called()

    @patch("users.recurring.merchant_request", return_value={"error_code": -1})
    @patch("users.notifications.send_telegram_message")
    def test_declined_payment_disables_renewal(self, notify, api):
        renewal = self.renewal()
        self.assertEqual(charge_due(renewal.pk), "failed")
        self.assertEqual(charge_due(renewal.pk), "skipped")
        notify.assert_called_once()

    @patch("users.recurring.merchant_request", side_effect=RenewalError("timeout"))
    def test_cleanup_preserves_unresolved_debit(self, api):
        renewal = self.renewal()
        charge_due(renewal.pk)
        cleanup_stale_click_orders(all_unpaid=True)
        self.assertEqual(ClickRenewalAttempt.objects.get().order.status, "pending")

    def test_setup_is_csrf_protected_and_requires_paid_order(self):
        url = reverse("click-renewal-setup", args=[self.order.order_id])
        client = Client(enforce_csrf_checks=True)
        self.assertEqual(client.get(url).status_code, 200)
        self.assertEqual(client.post(url, {}).status_code, 403)
        self.order.status = "pending"
        self.order.save()
        self.assertEqual(client.get(url).status_code, 403)

    def test_lifetime_and_expired_link_cannot_enroll(self):
        self.subscription.expires_at = None
        self.subscription.save()
        url = reverse("click-renewal-setup", args=[self.order.order_id])
        self.assertEqual(self.client.get(url).status_code, 403)

    @patch("users.recurring.merchant_request")
    def test_changed_duration_and_lifetime_disable_charging(self, api):
        renewal = self.renewal()
        self.plan.duration = 2
        self.plan.save()
        self.assertEqual(charge_due(renewal.pk), "disabled")
        renewal.enabled = True
        renewal.save()
        self.plan.period = "lifetime"
        self.plan.save()
        self.assertEqual(charge_due(renewal.pk), "disabled")
        api.assert_not_called()

    @patch("users.recurring.merchant_request", return_value={"error_code": 0, "card_token": "token"})
    def test_binding_cooldown(self, api):
        request_binding(self.order, "8600000000000000", "1228", True)
        with self.assertRaises(RenewalError):
            request_binding(self.order, "8600000000000000", "1228", True)
        self.assertEqual(api.call_count, 1)

    def test_expired_enrollment_link(self):
        self.order.paid_at = timezone.now() - timedelta(days=2)
        self.order.save()
        url = reverse("click-renewal-setup", args=[self.order.order_id])
        self.assertEqual(self.client.get(url).status_code, 403)

    @override_settings(CLICK_RENEWALS_ENABLED=False)
    @patch("users.recurring.merchant_request")
    def test_global_switch_stops_debits(self, api):
        renewal = self.renewal()
        self.assertEqual(charge_due(renewal.pk), "disabled")
        api.assert_not_called()
