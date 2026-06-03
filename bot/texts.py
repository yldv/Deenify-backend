from core.constants import DEFAULT_LANGUAGE, SUPPORTED_LANGUAGES

from bot.constants import BOT_UI_LANGUAGES

LANGUAGE_BUTTON_UZ = "🇺🇿 O'zbekcha"
LANGUAGE_BUTTON_UZ_CY = "🇺🇿 Ўзбекча"
LANGUAGE_BUTTON_RU = "🇷🇺 Русский"

LANGUAGE_BUTTON_TO_CODE = {
    LANGUAGE_BUTTON_UZ: "uz",
    LANGUAGE_BUTTON_UZ_CY: "uz_cy",
    LANGUAGE_BUTTON_RU: "ru",
}

LANGUAGE_BUTTON_TO_CODE_UI = {
    label: code
    for label, code in LANGUAGE_BUTTON_TO_CODE.items()
    if code in BOT_UI_LANGUAGES
}

LANGUAGE_BUTTON_TEXTS = list(LANGUAGE_BUTTON_TO_CODE_UI.keys())


def all_button_texts(key):
    return {get_text(lang, key) for lang in SUPPORTED_LANGUAGES}


TEXTS = {
    "uz": {
        "choose_language": "🌐 Tilni tanlang",
        "choose_language_button_hint": "🌐 Quyidagi tugmalardan tilni tanlang",
        "phone_prompt": "📱 Iltimos, telefon raqamingizni yuboring",
        "phone_invalid": "📱 Iltimos, telefon raqamingizni pastdagi tugma orqali yuboring.",
        "registration_success": "✅ Rahmat, siz muvaffaqiyatli ro'yxatdan o'tdingiz.",
        "home_menu": "📿 Siz bosh menyudasiz.\nIltimos, kerakli bo'limni tanlang ⬇️",
        "take_test": "📖 Test yechish",
        "restart_from_start": "🔄 Boshidan boshlash",
        "help": "📞 Yordam",
        "settings": "⚙️ Sozlamalar",
        "settings_section": "⚙️ Sozlamalar bo'limi",
        "change_language": "🌐 Tilni o'zgartirish",
        "language_updated": "✅ Til muvaffaqiyatli o'zgartirildi.",
        "back": "⬅️ Orqaga",
        "help_intro": (
            "Buyruqlar:\n"
            "/start — Botni qaytadan ishga tushirish\n"
            "/menu — Bosh menyu\n"
            "/test — Test yechish\n"
            "/restart — Testni boshidan boshlash (0 dan)\n"
            "/settings — Sozlamalar\n"
            "/help — Yordam\n\n"
            "Quyidan yordam turini tanlang. Agar javob topilmasa, operator bilan bog'laning."
        ),
        "help_phone": "📞 Telefon orqali bog'lanish",
        "help_message": "📬 Xabar jo'natish",
        "help_phone_number": "Bizning raqam: {phone}",
        "help_phone_missing": "Operator raqami hozircha sozlanmagan.",
        "help_message_prompt": "Bizga o'z xabaringizni jo'nating:",
        "help_message_empty": "❌ Xabar yozing.",
        "help_message_sent": "✅ Xabaringiz yuborildi.",
        "help_cancel": "Bekor qilish",
        "quiz_no_questions": "Hozircha savollar topilmadi.",
        "quiz_correct": "✅ To'g'ri!",
        "quiz_wrong": "❌ Noto'g'ri.",
        "quiz_progress": "📊 O'tilgan: {answered}/{total}",
        "quiz_round_complete": (
            "🎉 Tabriklaymiz! Siz barcha savollarni tugatdingiz.\n"
            "Qayta boshlash uchun «Boshidan boshlash» yoki «Test yechish» tugmasini bosing."
        ),
        "quiz_reset_hint": "✨ Test boshidan boshlandi.",
        "quiz_subscription_required": (
            "🔒 Bepul {free_limit} ta savoldan keyin davom etish uchun obuna kerak.\n"
            "To'lov tez orada qo'shiladi."
        ),
        "quiz_restart_hint": "✨ Test qayta boshlandi. Barcha savollar boshidan, tasodifiy tartibda.",
        "quiz_session_expired": (
            "⏳ Bu savol muddati tugadi (bot qayta ishga tushgan bo'lishi mumkin).\n"
            "«Test yechish» tugmasini bosing."
        ),
        "blocked": "Akkount bloklangan.",
        "not_found": "Ma'lumot topilmadi. /start ni bosing.",
        "error": "Xatolik yuz berdi. Keyinroq urinib ko'ring.",
        "share_phone": "📱 Raqamni yuborish",
    },
    "uz_cy": {
        "choose_language": "🌐 Тилни танланг",
        "choose_language_button_hint": "🌐 Қуйидаги тугмалардан тилни танланг",
        "phone_prompt": "📱 Илтимос, телефон рақамингизни юборинг",
        "phone_invalid": "📱 Илтимос, телефон рақамингизни пастдаги тугма орқали юборинг.",
        "registration_success": "✅ Рахмат, сиз муваффақиятли рўйхатдан ўтдингиз.",
        "home_menu": "📿 Сиз бош менюдасиз.\nИлтимос, керакли бўлимни танланг ⬇️",
        "take_test": "📖 Тест ечиш",
        "restart_from_start": "🔄 Бошидан бошлаш",
        "help": "📞 Ёрдам",
        "settings": "⚙️ Созламалар",
        "settings_section": "⚙️ Созламалар бўлими",
        "change_language": "🌐 Тилни ўзгартириш",
        "language_updated": "✅ Тил муваффақиятли ўзгартирилди.",
        "back": "⬅️ Орқага",
        "help_intro": (
            "Буйруқлар:\n"
            "/start — Ботни қайта ишга тушириш\n"
            "/menu — Бош меню\n"
            "/test — Тест ечиш\n"
            "/restart — Тестни бошидан бошлаш (0 дан)\n"
            "/settings — Созламалар\n"
            "/help — Ёрдам\n\n"
            "Қуйида ёрдам турини танланг. Агар жавоб топилмаса, оператор билан боғланинг."
        ),
        "help_phone": "📞 Телефон орқали боғланиш",
        "help_message": "📬 Хабар жўнатиш",
        "help_phone_number": "Бизнинг рақам: {phone}",
        "help_phone_missing": "Оператор рақами ҳозирча созланмаган.",
        "help_message_prompt": "Бизга ўз хабарингизни жўнатинг:",
        "help_message_empty": "❌ Хабар ёзинг.",
        "help_message_sent": "✅ Хабарингиз юборилди.",
        "help_cancel": "Бекор қилиш",
        "quiz_no_questions": "Ҳозирча саволлар топилмади.",
        "quiz_correct": "✅ Тўғри!",
        "quiz_wrong": "❌ Нотўғри.",
        "quiz_progress": "📊 Ўтилган: {answered}/{total}",
        "quiz_round_complete": (
            "🎉 Табриклаймиз! Сиз барча саволларни тугатдингиз.\n"
            "Қайта бошлаш учун «Бошидан бошлаш» ёки «Тест ечиш» тугмасини босинг."
        ),
        "quiz_reset_hint": "✨ Тест бошидан бошланди.",
        "quiz_subscription_required": (
            "🔒 Бепул {free_limit} та саволдан кейин давом этиш учун обуна керак.\n"
            "Тўлов тез орада қўшилади."
        ),
        "quiz_restart_hint": "✨ Тест қайта бошланди. Барча саволлар бошидан, тасодифий тартибда.",
        "quiz_session_expired": (
            "⏳ Бу savol muddati tugadi (bot qayta ishga tushgan bo'lishi mumkin).\n"
            "«Тест ечиш» tugmasini bosing."
        ),
        "blocked": "Аккаунт блокланган.",
        "not_found": "Маълумот топилмади. /start ни босинг.",
        "error": "Хатолик юз берди. Кейинроқ уриниб кўринг.",
        "share_phone": "📱 Рақамни юбориш",
    },
    "ru": {
        "choose_language": "🌐 Tilni tanlang / Выберите язык",
        "choose_language_button_hint": "🌐 Tilni tugma orqali tanlang / Выберите язык кнопкой",
        "phone_prompt": "📱 Пожалуйста, отправьте ваш номер телефона",
        "phone_invalid": "📱 Пожалуйста, отправьте номер телефона кнопкой ниже.",
        "registration_success": "✅ Спасибо, вы успешно зарегистрированы.",
        "home_menu": "📿 Вы в главном меню.\nПожалуйста, выберите нужный раздел ⬇️",
        "take_test": "📖 Пройти тест",
        "restart_from_start": "🔄 С начала",
        "help": "📞 Помощь",
        "settings": "⚙️ Настройки",
        "settings_section": "⚙️ Раздел настроек",
        "change_language": "🌐 Сменить язык",
        "language_updated": "✅ Язык успешно изменён.",
        "back": "⬅️ Назад",
        "help_intro": (
            "Команды:\n"
            "/start — Перезапуск бота\n"
            "/menu — Главное меню\n"
            "/test — Пройти тест\n"
            "/restart — Начать тест с нуля\n"
            "/settings — Настройки\n"
            "/help — Помощь\n\n"
            "Ниже выберите тип помощи. Если не найдёте ответ, свяжитесь с оператором."
        ),
        "help_phone": "📞 Связаться по телефону",
        "help_message": "📬 Отправить сообщение",
        "help_phone_number": "Наш номер: {phone}",
        "help_phone_missing": "Номер оператора пока не настроен.",
        "help_message_prompt": "Отправьте нам ваше сообщение:",
        "help_message_empty": "❌ Напишите сообщение.",
        "help_message_sent": "✅ Ваше сообщение отправлено.",
        "help_cancel": "Отмена",
        "quiz_no_questions": "Вопросы пока не найдены.",
        "quiz_correct": "✅ Правильно!",
        "quiz_wrong": "❌ Неправильно.",
        "quiz_progress": "📊 Прогресс: {answered}/{total}",
        "quiz_round_complete": (
            "🎉 Поздравляем! Вы завершили все вопросы.\n"
            "Нажмите «С начала» или «Пройти тест», чтобы начать заново."
        ),
        "quiz_reset_hint": "✨ Тест начат с начала.",
        "quiz_subscription_required": (
            "🔒 После {free_limit} бесплатных вопросов нужна подписка.\n"
            "Оплата скоро будет доступна."
        ),
        "quiz_restart_hint": "✨ Тест начат заново. Все вопросы с начала, в случайном порядке.",
        "blocked": "Аккаунт заблокирован.",
        "not_found": "Данные не найдены. Нажмите /start.",
        "error": "Произошла ошибка. Попробуйте позже.",
        "share_phone": "📱 Поделиться номером",
    },
}


def normalize_language(language):
    return language if language in SUPPORTED_LANGUAGES else DEFAULT_LANGUAGE


def get_text(language, key, **kwargs):
    language = normalize_language(language)
    template = TEXTS[language].get(key, TEXTS[DEFAULT_LANGUAGE].get(key, key))
    return template.format(**kwargs) if kwargs else template
