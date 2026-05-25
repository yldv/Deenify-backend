from django.core.management.base import BaseCommand
from django.db import transaction

from bot.uz_cyrillic import latin_to_cyrillic
from tests.models import Answer, Test, TestCategory
from tests.seed_data.quiz_questions import get_quiz_questions
from users.models import SubscriptionPlan

TRANSLATION_LANGS = ("uz", "ru", "uz_cy")


def ensure_translations(translations):
    result = dict(translations)
    if "uz" in result and "uz_cy" not in result:
        result["uz_cy"] = latin_to_cyrillic(result["uz"])
    return result


def translated_defaults(model, values):
    defaults = {}
    field_names = {field.name for field in model._meta.get_fields()}
    for field, raw_translations in values.items():
        
        translations = ensure_translations(raw_translations)
        normal_value = translations.get("uz") or translations.get("ru") or ""
        if field in field_names:
            defaults[field] = normal_value
        for language in TRANSLATION_LANGS:
            value = translations.get(language)
            if value is None:
                continue
            translated_field = f"{field}_{language}"
            if translated_field in field_names:
                defaults[translated_field] = value
    return defaults


class Command(BaseCommand):
    help = "Seed Deenify islam quiz: 50 tests (20 easy, 15 medium, 15 hard)."

    @transaction.atomic
    def handle(self, *args, **options):
        category = self.seed_default_category()
        self.seed_subscription_plans()
        count = self.seed_tests(category)
        self.stdout.write(self.style.SUCCESS(f"Deenify seed: {count} tests upserted."))

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

    def seed_tests(self, category):
        Test.objects.exclude(category=category).update(is_active=False)
        Test.objects.filter(category=category).update(is_active=False)

        for item in get_quiz_questions():
            defaults = {
                "category": category,
                "level": item["level"],
                "is_active": True,
                "is_premium": False,
                "sort_order": item["sort_order"],
                **translated_defaults(
                    Test,
                    {
                        "title": item["title"],
                        "question": item["question"],
                        "description": item["description"],
                        "explanation": item["explanation"],
                    },
                ),
            }
            test, _ = Test.objects.update_or_create(
                category=category,
                level=item["level"],
                sort_order=item["sort_order"],
                defaults=defaults,
            )
            self.seed_answers(test, item["answers"])

        return Test.objects.filter(category=category, is_active=True).count()

    def seed_answers(self, test, answers):
        test.answers.update(is_correct=False)
        for index, (is_correct, text) in enumerate(answers, start=1):
            answer = test.answers.filter(sort_order=index).first()
            defaults = {
                "is_correct": is_correct,
                "sort_order": index,
                **translated_defaults(Answer, {"text": text}),
            }
            if answer:
                for field, value in defaults.items():
                    setattr(answer, field, value)
                answer.save(update_fields=tuple(defaults.keys()) + ("updated_at",))
            else:
                Answer.objects.create(test=test, **defaults)
