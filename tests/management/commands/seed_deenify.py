from django.core.management.base import BaseCommand
from django.db import transaction

from tests.models import Test, TestCategory
from tests.seed_data.quiz_questions import get_quiz_questions
from tests.services.quiz_import import import_questions_from_payload
from tests.services.translation_utils import translated_defaults
from users.models import SubscriptionPlan

TRANSLATION_LANGS = ("uz", "ru", "uz_cy")


class Command(BaseCommand):
    help = "Seed Deenify islam quiz: 50 tests (20 easy, 15 medium, 15 hard)."

    @transaction.atomic
    def handle(self, *args, **options):
        category = self.seed_default_category()
        self.seed_subscription_plans()
        result = import_questions_from_payload(
            {
                "category_slug": category.slug,
                "deactivate_others": True,
                "questions": get_quiz_questions(),
            },
            category_slug=category.slug,
            deactivate_others=True,
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"Deenify seed: {result['imported']} tests upserted "
                f"({result['active_questions']} active)."
            )
        )

    def seed_default_category(self):
        defaults = {
            "is_active": True,
            "sort_order": 0,
            **translated_defaults(
                TestCategory,
                {
                    "name": {
                        "uz": "Islom savollari",
                        "ru": "Исламские вопросы",
                    },
                    "description": {
                        "uz": "Islom bo'yicha test savollari",
                        "ru": "Тестовые вопросы по исламу",
                    },
                },
            ),
        }
        category, _ = TestCategory.objects.update_or_create(slug="islam", defaults=defaults)
        return category

    def seed_subscription_plans(self):
        plans = [
            {
                "price": "29000.00",
                "duration": 1,
                "period": SubscriptionPlan.BillingPeriod.MONTH,
                "sort_order": 1,
                "name": {"uz": "Oylik Premium", "ru": "Premium на месяц"},
                "description": {
                    "uz": "30 kun davomida cheksiz testlar",
                    "ru": "Безлимитные тесты на 30 дней",
                },
            },
            {
                "price": "249000.00",
                "duration": 1,
                "period": SubscriptionPlan.BillingPeriod.YEAR,
                "sort_order": 2,
                "name": {"uz": "Yillik Premium", "ru": "Premium на год"},
                "description": {
                    "uz": "365 kun davomida cheksiz testlar",
                    "ru": "Безлимитные тесты на 365 дней",
                },
            },
        ]
        for item in plans:
            plan = (
                SubscriptionPlan.objects.filter(
                    period=item["period"],
                    duration=item["duration"],
                    price=item["price"],
                )
                .order_by("id")
                .first()
            )
            defaults = {
                "price": item["price"],
                "currency": "UZS",
                "duration": item["duration"],
                "period": item["period"],
                "is_active": True,
                "sort_order": item["sort_order"],
                **translated_defaults(
                    SubscriptionPlan,
                    {"name": item["name"], "description": item["description"]},
                ),
            }
            if plan:
                for field, value in defaults.items():
                    setattr(plan, field, value)
                plan.save(update_fields=tuple(defaults.keys()) + ("updated_at",))
            else:
                SubscriptionPlan.objects.create(**defaults)
