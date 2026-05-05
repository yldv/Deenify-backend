from django.core.management.base import BaseCommand
from django.db import transaction

from tests.models import Answer, Test, TestCategory
from users.models import SubscriptionPlan


def translated_defaults(model, values):
    defaults = {}
    field_names = {field.name for field in model._meta.get_fields()}
    for field, translations in values.items():
        normal_value = translations.get("en") or translations.get("uz") or ""
        if field in field_names:
            defaults[field] = normal_value
        for language, value in translations.items():
            translated_field = f"{field}_{language}"
            if translated_field in field_names:
                defaults[translated_field] = value
    return defaults


def update_translated(instance, values):
    defaults = translated_defaults(type(instance), values)
    for field, value in defaults.items():
        setattr(instance, field, value)
    instance.save(update_fields=tuple(defaults.keys()) + ("updated_at",))
    return instance


class Command(BaseCommand):
    help = "Seed initial Deenify categories, subscription plans, tests, and answers."

    @transaction.atomic
    def handle(self, *args, **options):
        categories = self.seed_categories()
        self.seed_subscription_plans()
        self.seed_tests(categories["general"])
        self.stdout.write(self.style.SUCCESS("Deenify seed data created/updated."))

    def seed_categories(self):
        data = [
            {
                "slug": "general",
                "sort_order": 1,
                "name": {
                    "uz": "Umumiy testlar",
                    "ru": "Общие тесты",
                    "en": "General tests",
                },
                "description": {
                    "uz": "Boshlang‘ich test savollari",
                    "ru": "Базовые тестовые вопросы",
                    "en": "Basic test questions",
                },
            },
            {
                "slug": "deen-basics",
                "sort_order": 2,
                "name": {
                    "uz": "Din asoslari",
                    "ru": "Основы религии",
                    "en": "Deen basics",
                },
                "description": {
                    "uz": "Islom asoslari bo‘yicha savollar",
                    "ru": "Вопросы по основам ислама",
                    "en": "Questions about Islamic basics",
                },
            },
        ]
        categories = {}
        for item in data:
            defaults = {
                "is_active": True,
                "sort_order": item["sort_order"],
                **translated_defaults(
                    TestCategory,
                    {
                        "name": item["name"],
                        "description": item["description"],
                    },
                ),
            }
            category, _ = TestCategory.objects.update_or_create(
                slug=item["slug"],
                defaults=defaults,
            )
            categories[item["slug"]] = category
        return categories

    def seed_subscription_plans(self):
        plans = [
            {
                "key": "monthly",
                "price": "29000.00",
                "duration": 1,
                "period": SubscriptionPlan.BillingPeriod.MONTH,
                "sort_order": 1,
                "name": {
                    "uz": "Oylik Premium",
                    "ru": "Premium на месяц",
                    "en": "Monthly Premium",
                },
                "description": {
                    "uz": "30 kun davomida cheksiz testlar",
                    "ru": "Безлимитные тесты на 30 дней",
                    "en": "Unlimited tests for 30 days",
                },
            },
            {
                "key": "yearly",
                "price": "249000.00",
                "duration": 1,
                "period": SubscriptionPlan.BillingPeriod.YEAR,
                "sort_order": 2,
                "name": {
                    "uz": "Yillik Premium",
                    "ru": "Premium на год",
                    "en": "Yearly Premium",
                },
                "description": {
                    "uz": "365 kun davomida cheksiz testlar",
                    "ru": "Безлимитные тесты на 365 дней",
                    "en": "Unlimited tests for 365 days",
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
                    {
                        "name": item["name"],
                        "description": item["description"],
                    },
                ),
            }
            if plan:
                for field, value in defaults.items():
                    setattr(plan, field, value)
                plan.save(update_fields=tuple(defaults.keys()) + ("updated_at",))
            else:
                SubscriptionPlan.objects.create(**defaults)

    def seed_tests(self, category):
        tests = [
            {
                "level": Test.Level.EASY,
                "sort_order": 1,
                "title": {
                    "uz": "Islomning birinchi rukni",
                    "ru": "Первый столп ислама",
                    "en": "First pillar of Islam",
                },
                "question": {
                    "uz": "Islomning birinchi rukni nima?",
                    "ru": "Каков первый столп ислама?",
                    "en": "What is the first pillar of Islam?",
                },
                "explanation": {
                    "uz": "Islomning birinchi rukni shahodat keltirishdir.",
                    "ru": "Первый столп ислама — свидетельство веры.",
                    "en": "The first pillar of Islam is the testimony of faith.",
                },
                "answers": [
                    (True, {"uz": "Shahodat", "ru": "Шахада", "en": "Shahada"}),
                    (False, {"uz": "Ro‘za", "ru": "Пост", "en": "Fasting"}),
                    (False, {"uz": "Zakot", "ru": "Закят", "en": "Zakat"}),
                    (False, {"uz": "Haj", "ru": "Хадж", "en": "Hajj"}),
                ],
            },
            {
                "level": Test.Level.EASY,
                "sort_order": 2,
                "title": {
                    "uz": "Kunlik namozlar",
                    "ru": "Ежедневные молитвы",
                    "en": "Daily prayers",
                },
                "question": {
                    "uz": "Bir kunda necha mahal farz namoz o‘qiladi?",
                    "ru": "Сколько обязательных молитв совершается в день?",
                    "en": "How many obligatory prayers are performed daily?",
                },
                "explanation": {
                    "uz": "Musulmonlar bir kunda besh mahal farz namoz o‘qiydi.",
                    "ru": "Мусульмане совершают пять обязательных молитв в день.",
                    "en": "Muslims perform five obligatory prayers daily.",
                },
                "answers": [
                    (False, {"uz": "3", "ru": "3", "en": "3"}),
                    (True, {"uz": "5", "ru": "5", "en": "5"}),
                    (False, {"uz": "7", "ru": "7", "en": "7"}),
                    (False, {"uz": "10", "ru": "10", "en": "10"}),
                ],
            },
            {
                "level": Test.Level.MEDIUM,
                "sort_order": 3,
                "title": {
                    "uz": "Qibla yo‘nalishi",
                    "ru": "Направление киблы",
                    "en": "Qibla direction",
                },
                "question": {
                    "uz": "Namozda qaysi tomonga yuzlaniladi?",
                    "ru": "В какую сторону обращаются во время намаза?",
                    "en": "Which direction does one face during prayer?",
                },
                "explanation": {
                    "uz": "Namozda Ka’ba tomonga, ya’ni qiblaga yuzlaniladi.",
                    "ru": "Во время намаза обращаются к Каабе, то есть к кибле.",
                    "en": "During prayer, one faces the Kaaba, the qibla.",
                },
                "answers": [
                    (True, {"uz": "Ka’ba tomonga", "ru": "К Каабе", "en": "Toward the Kaaba"}),
                    (False, {"uz": "Shimolga", "ru": "На север", "en": "North"}),
                    (False, {"uz": "Sharqqa", "ru": "На восток", "en": "East"}),
                    (False, {"uz": "Istalgan tomonga", "ru": "В любую сторону", "en": "Any direction"}),
                ],
            },
            {
                "level": Test.Level.MEDIUM,
                "sort_order": 4,
                "title": {
                    "uz": "Zakot hukmi",
                    "ru": "Положение закята",
                    "en": "Ruling of zakat",
                },
                "question": {
                    "uz": "Zakot Islomda qanday amal hisoblanadi?",
                    "ru": "Чем является закят в исламе?",
                    "en": "What is zakat considered in Islam?",
                },
                "explanation": {
                    "uz": "Zakot Islomning farz ruknlaridan biridir.",
                    "ru": "Закят является одним из обязательных столпов ислама.",
                    "en": "Zakat is one of the obligatory pillars of Islam.",
                },
                "answers": [
                    (False, {"uz": "Ixtiyoriy sadaqa", "ru": "Добровольная милостыня", "en": "Voluntary charity"}),
                    (True, {"uz": "Farz amal", "ru": "Обязательное действие", "en": "Obligatory act"}),
                    (False, {"uz": "Faqat odat", "ru": "Только обычай", "en": "Only a custom"}),
                    (False, {"uz": "Makruh amal", "ru": "Нежелательное действие", "en": "Disliked act"}),
                ],
            },
            {
                "level": Test.Level.HARD,
                "sort_order": 5,
                "title": {
                    "uz": "Ramazon ro‘zasi",
                    "ru": "Пост Рамадана",
                    "en": "Ramadan fasting",
                },
                "question": {
                    "uz": "Ramazon ro‘zasi kimlarga farz bo‘ladi?",
                    "ru": "Для кого обязателен пост Рамадана?",
                    "en": "For whom is Ramadan fasting obligatory?",
                },
                "explanation": {
                    "uz": "Ramazon ro‘zasi balog‘atga yetgan, aqli joyida, qodir musulmonlarga farzdir.",
                    "ru": "Пост Рамадана обязателен для совершеннолетних, разумных и способных мусульман.",
                    "en": "Ramadan fasting is obligatory for adult, sane, capable Muslims.",
                },
                "answers": [
                    (True, {"uz": "Qodir musulmonlarga", "ru": "Способным мусульманам", "en": "Capable Muslims"}),
                    (False, {"uz": "Faqat bolalarga", "ru": "Только детям", "en": "Only children"}),
                    (False, {"uz": "Faqat musofirlarga", "ru": "Только путникам", "en": "Only travelers"}),
                    (False, {"uz": "Hech kimga", "ru": "Никому", "en": "No one"}),
                ],
            },
            {
                "level": Test.Level.HARD,
                "sort_order": 6,
                "title": {
                    "uz": "Haj ibodati",
                    "ru": "Паломничество хадж",
                    "en": "Hajj pilgrimage",
                },
                "question": {
                    "uz": "Haj ibodati kimlarga farz?",
                    "ru": "Для кого обязателен хадж?",
                    "en": "For whom is Hajj obligatory?",
                },
                "explanation": {
                    "uz": "Haj moliyaviy va jismoniy imkoniyatga ega musulmonlarga umrida bir marta farz.",
                    "ru": "Хадж обязателен один раз в жизни для мусульман, имеющих физическую и финансовую возможность.",
                    "en": "Hajj is obligatory once in a lifetime for Muslims with physical and financial ability.",
                },
                "answers": [
                    (False, {"uz": "Har kuni hammaga", "ru": "Каждый день всем", "en": "Everyone every day"}),
                    (True, {"uz": "Imkoniyati bor musulmonlarga", "ru": "Мусульманам с возможностью", "en": "Muslims who are able"}),
                    (False, {"uz": "Faqat kambag‘allarga", "ru": "Только бедным", "en": "Only the poor"}),
                    (False, {"uz": "Faqat bolalarga", "ru": "Только детям", "en": "Only children"}),
                ],
            },
        ]

        for item in tests:
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
