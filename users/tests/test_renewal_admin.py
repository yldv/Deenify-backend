from datetime import timedelta

from django.contrib import admin
from django.test import TestCase
from django.utils import timezone

from users.admin import RenewalScheduleForm
from users.models import ClickOrder, ClickRenewal, ClickRenewalAttempt, SubscriptionPlan, TelegramUser


class RenewalScheduleAdminTests(TestCase):
    def setUp(self):
        self.user = TelegramUser.objects.create(telegram_id=12345)
        self.plan = SubscriptionPlan.objects.create(name="Monthly", price=1000, duration=1, period="month")
        self.renewal = ClickRenewal.objects.create(user=self.user, plan=self.plan, amount=1000,
            period="month", duration=1, enabled=True, verified=True,
            next_charge_at=timezone.now() + timedelta(days=30))

    def test_schedule_edit_does_not_change_billing_authorization(self):
        target = timezone.now() + timedelta(days=31)
        form = RenewalScheduleForm({"next_charge_at": target.isoformat(), "enabled": False, "amount": 1}, instance=self.renewal)
        self.assertTrue(form.is_valid(), form.errors)
        model_admin = admin.site._registry[ClickRenewal]
        model_admin.save_model(None, form.save(commit=False), form, True)
        self.renewal.refresh_from_db()
        self.assertEqual(self.renewal.next_charge_at, target)
        self.assertTrue(self.renewal.enabled)
        self.assertEqual(self.renewal.amount, 1000)
        self.assertEqual(list(form.fields), ["next_charge_at"])

    def test_uncertain_debit_cannot_be_bypassed_by_changing_due_time(self):
        order = ClickOrder.create_for_plan(self.user, self.plan)
        ClickRenewalAttempt.objects.create(renewal=self.renewal, order=order,
                                          due_at=self.renewal.next_charge_at, state="uncertain")
        form = RenewalScheduleForm({"next_charge_at": (timezone.now() + timedelta(days=32)).isoformat()}, instance=self.renewal)
        self.assertFalse(form.is_valid())
        self.assertIn("next_charge_at", form.errors)

    def test_enabled_renewal_requires_a_scheduled_time(self):
        form = RenewalScheduleForm({"next_charge_at": ""}, instance=self.renewal)
        self.assertFalse(form.is_valid())
