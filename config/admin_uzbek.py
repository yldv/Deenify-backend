"""O'zbekcha admin: ilova va model nomlari, maydon yorliqlari, tanlov matnlari."""

from django.apps import apps

_APPLIED = False

APP_VERBOSE = {
    "auth": "Tizim sozlamalari",
    "users": "Bot foydalanuvchilari",
    "tests": "Test savollari",
}

MODEL_VERBOSE = {
    ("auth", "user"): ("Administrator", "Administratorlar"),
    ("auth", "group"): ("Guruh", "Guruhlar"),
    ("users", "telegramuser"): ("Telegram foydalanuvchi", "Telegram foydalanuvchilar"),
    ("users", "activetelegramuser"): (
        "Faol Telegram foydalanuvchi",
        "Faol Telegram foydalanuvchilar",
    ),
    ("users", "subscriptionplan"): ("Obuna rejasi", "Obuna rejalari"),
    ("users", "userpremiumsubscription"): ("Premium obuna", "Premium obunalar"),
    ("users", "boundcard"): ("Bog'langan karta", "Bog'langan kartalar"),
    ("users", "feedback"): ("Fikr-mulohaza", "Fikr-mulohazalar"),
    ("users", "atmosorder"): ("To'lov buyurtmasi", "To'lov buyurtmalari"),
    ("users", "atmostransaction"): ("To'lov tranzaksiyasi", "To'lov tranzaksiyalari"),
    ("tests", "test"): ("Test savoli", "Test savollari"),
    ("tests", "testcategory"): ("Kategoriya", "Kategoriyalar"),
    ("tests", "answer"): ("Javob varianti", "Javob variantlari"),
    ("tests", "useransweredtest"): ("Foydalanuvchi javobi", "Foydalanuvchi javoblari"),
}

FIELD_VERBOSE = {
    "telegram_id": "Telegram ID",
    "username": "Telegram username",
    "full_name": "To'liq ism",
    "first_name": "Ism",
    "last_name": "Familiya",
    "phone_number": "Telefon raqami",
    "phone": "Telefon",
    "language": "Til",
    "quiz_round": "Test bosqichi",
    "free_tests_taken": "Bepul testlar soni",
    "is_blocked": "Bloklangan (admin)",
    "bot_is_active": "Bot faol",
    "is_active": "Faol",
    "is_premium": "Premium savol",
    "is_correct": "To'g'ri javob",
    "sort_order": "Tartib raqami",
    "created_at": "Yaratilgan vaqt",
    "updated_at": "Yangilangan vaqt",
    "last_seen_at": "Oxirgi faollik",
    "removed_at": "Uzilgan vaqt",
    "title": "Sarlavha",
    "title_uz": "Sarlavha (lotin)",
    "title_uz_cy": "Sarlavha (kirill)",
    "title_ru": "Sarlavha (rus)",
    "question": "Savol matni",
    "question_uz": "Savol (lotin)",
    "question_uz_cy": "Savol (kirill)",
    "question_ru": "Savol (rus)",
    "description_uz": "Manba (lotin)",
    "description_uz_cy": "Manba (kirill)",
    "description_ru": "Manba (rus)",
    "explanation_uz": "Tushuntirish (lotin)",
    "explanation_uz_cy": "Tushuntirish (kirill)",
    "explanation_ru": "Tushuntirish (rus)",
    "text_uz": "Javob (lotin)",
    "text_uz_cy": "Javob (kirill)",
    "text_ru": "Javob (rus)",
    "name_uz": "Nomi (lotin)",
    "name_uz_cy": "Nomi (kirill)",
    "name_ru": "Nomi (rus)",
    "description": "Tavsif",
    "explanation": "Tushuntirish",
    "level": "Daraja",
    "category": "Kategoriya",
    "slug": "Slug (texnik)",
    "text": "Matn",
    "test": "Savol",
    "user": "Foydalanuvchi",
    "round": "Bosqich",
    "price": "Narx",
    "currency": "Valyuta",
    "duration": "Davomiylik",
    "period": "Davr",
    "name": "Nomi",
    "plan": "Reja",
    "starts_at": "Boshlanish",
    "expires_at": "Tugash",
    "amount": "Summa",
    "status": "Holat",
    "paid_at": "To'langan vaqt",
    "order_id": "Buyurtma ID",
    "merchant_order_id": "Merchant ID",
    "source_order": "Manba buyurtma",
    "atmos_transaction_id": "Atmos tranzaksiya ID",
    "transaction_id": "Tranzaksiya ID",
    "payment_url": "To'lov havolasi",
    "request_payload": "So'rov ma'lumotlari",
    "response_payload": "Javob ma'lumotlari",
    "provider_payload": "Provayder ma'lumotlari",
    "performed_at": "Bajarilgan vaqt",
    "success_notified": "Muvaffaqiyat xabari yuborilgan",
    "is_auto_renewal": "Avtomatik yangilash",
    "auto_renew": "Avto-uzaytirish",
    "source": "Manba",
    "bound_card": "Bog'langan karta",
    "card_id": "Atmos karta ID",
    "card_token": "Karta tokeni (maxfiy)",
    "masked_pan": "Karta raqami (yashirin)",
    "expiry": "Amal qilish muddati",
    "card_holder": "Karta egasi",
    "referred_by": "Kim taklif qilgan",
    "referral_rewarded": "Referral mukofoti berilgan",
    "offer_message_id": "Taklif xabari ID",
    "offer_chat_id": "Taklif chat ID",
    "offer_prompt_message_id": "Taklif oldi xabari ID",
    "offer_sent_at": "Taklif yuborilgan vaqt",
    "context": "Kontekst",
    "reason": "Sabab",
    "order": "Buyurtma",
    "password": "Parol",
    "last_login": "Oxirgi kirish",
    "is_staff": "Xodim",
    "is_superuser": "Superadmin",
    "email": "Email",
    "date_joined": "Ro'yxatdan o'tgan",
    "groups": "Guruhlar",
    "permissions": "Ruxsatlar",
}

LEVEL_LABELS = {
    "easy": "Oson",
    "medium": "O'rta",
    "hard": "Qiyin",
}

ORDER_STATUS_LABELS = {
    "created": "Yaratilgan",
    "pending": "Kutilmoqda",
    "paid": "To'langan",
    "canceled": "Bekor qilingan",
    "failed": "Xato",
    "expired": "Muddati o'tgan",
}

TRANSACTION_STATUS_LABELS = {
    "initiated": "Boshlangan",
    "success": "Muvaffaqiyatli",
    "failed": "Xato",
    "canceled": "Bekor qilingan",
    "reversed": "Qaytarilgan",
}

PERIOD_LABELS = {
    "day": "Kun",
    "week": "Hafta",
    "month": "Oy",
    "year": "Yil",
    "lifetime": "Abadiy",
}

SUBSCRIPTION_SOURCE_LABELS = {
    "payment": "To'lov",
    "referral": "Referral bonus",
    "manual": "Qo'lda",
}

LANGUAGE_LABELS = {
    "uz": "O'zbek (lotin)",
    "uz_cy": "O'zbek (kirill)",
    "ru": "Rus",
}

FEEDBACK_CONTEXT_LABELS = {
    "declined": "Taklif rad etildi",
    "canceled": "Obuna bekor qilindi",
}

FEEDBACK_REASON_LABELS = {
    "expensive": "Qimmat",
    "not_now": "Hozir kerak emas",
    "trust": "Ishonch / xavfsizlik",
    "hard_payment": "To'lov qiyin edi",
    "other": "Boshqa",
}

FIELD_CHOICE_LABELS = {
    ("users", "atmosorder", "status"): ORDER_STATUS_LABELS,
    ("users", "atmostransaction", "status"): TRANSACTION_STATUS_LABELS,
    ("users", "subscriptionplan", "period"): PERIOD_LABELS,
    ("users", "userpremiumsubscription", "source"): SUBSCRIPTION_SOURCE_LABELS,
    ("users", "telegramuser", "language"): LANGUAGE_LABELS,
    ("users", "feedback", "context"): FEEDBACK_CONTEXT_LABELS,
    ("users", "feedback", "reason"): FEEDBACK_REASON_LABELS,
    ("tests", "test", "level"): LEVEL_LABELS,
}


def _patch_field_choices(model, field_name, label_map):
    try:
        field = model._meta.get_field(field_name)
    except Exception:  # noqa: BLE001
        return
    if not getattr(field, "choices", None):
        return
    field.choices = [
        (value, label_map.get(value, label)) if value else (value, label)
        for value, label in field.choices
    ]


def apply_uzbek_admin():
    global _APPLIED
    if _APPLIED:
        return
    _APPLIED = True

    for app_label, verbose in APP_VERBOSE.items():
        try:
            app_config = apps.get_app_config(app_label)
            app_config.verbose_name = verbose
        except LookupError:
            continue

    for (app_label, model_name), (singular, plural) in MODEL_VERBOSE.items():
        try:
            model = apps.get_model(app_label, model_name)
        except LookupError:
            continue
        model._meta.verbose_name = singular
        model._meta.verbose_name_plural = plural
        for field in model._meta.get_fields():
            if hasattr(field, "verbose_name") and field.name in FIELD_VERBOSE:
                field.verbose_name = FIELD_VERBOSE[field.name]
        for field_name, label_map in (
            (key[2], labels)
            for key, labels in FIELD_CHOICE_LABELS.items()
            if key[0] == app_label and key[1] == model_name
        ):
            _patch_field_choices(model, field_name, label_map)
