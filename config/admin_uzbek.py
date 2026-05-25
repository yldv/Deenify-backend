"""O'zbekcha admin: ilova va model nomlari, maydon yorliqlari."""

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
    ("users", "subscriptionplan"): ("Obuna rejasi", "Obuna rejalari"),
    ("users", "userpremiumsubscription"): ("Premium obuna", "Premium obunalar"),
    ("users", "atmosorder"): ("To'lov buyurtmasi", "To'lov buyurtmalari"),
    ("users", "atmostransaction"): ("To'lov tranzaksiyasi", "To'lov tranzaksiyalari"),
    ("tests", "test"): ("Test savoli", "Test savollari"),
    
    ("tests", "answer"): ("Javob varianti", "Javob variantlari"),
    ("tests", "useransweredtest"): ("Foydalanuvchi javobi", "Foydalanuvchi javoblari"),
    ("tests", "usertestsession"): ("Test sessiyasi", "Test sessiyalari"),
    ("tests", "usertestanswer"): ("Sessiya javobi", "Sessiya javoblari"),
}

FIELD_VERBOSE = {
    "telegram_id": "Telegram ID",
    "username": "Telegram username",
    "full_name": "To'liq ism",
    "first_name": "Ism",
    "last_name": "Familiya",
    "phone_number": "Telefon raqami",
    "language": "Til",
    "quiz_round": "Test bosqichi",
    "free_tests_taken": "Bepul testlar soni",
    "is_blocked": "Bloklangan",
    "is_active": "Faol",
    "is_premium": "Premium savol",
    "is_correct": "To'g'ri javob",
    "sort_order": "Tartib raqami",
    "created_at": "Yaratilgan vaqt",
    "updated_at": "Yangilangan vaqt",
    "last_seen_at": "Oxirgi faollik",
    "title": "Sarlavha",
    "question": "Savol matni",
    "description": "Manba (poll ostida)",
    "explanation": "Tushuntirish",
    "level": "Daraja",
    "category": "Kategoriya",
    "slug": "Slug (texnik)",
    "text": "Javob matni",
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
    "total_questions": "Jami savollar",
    "correct_answers": "To'g'ri javoblar",
    "wrong_answers": "Noto'g'ri javoblar",
    "started_at": "Boshlangan",
    "completed_at": "Tugallangan",
    "answered_at": "Javob vaqti",
    "session": "Sessiya",
    "selected_answer": "Tanlangan javob",
    "source_order": "Manba buyurtma",
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
