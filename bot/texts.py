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
        "settings_subscription_active": (
            "📊 {plan}\n"
            "✅ Premium faol\n"
            "📅 Boshlandi: {starts}\n"
            "📅 Tugaydi: {until}"
        ),
        "settings_subscription_free": "📊 Premium: yo'q\n🆓 Bepul savollar: {used}/{limit}",
        "settings_subscription_free_exhausted": (
            "📊 Premium: yo'q\n"
            "🚫 Bepul limit tugadi ({used}/{limit})\n"
            "💎 Davom etish uchun obuna kerak"
        ),
        "settings_subscription_expired": (
            "📊 {plan}\n"
            "⏰ Premium muddati tugagan\n"
            "📅 Tugagan sana: {until}\n"
            "🆓 Bepul savollar: {used}/{limit}"
        ),
        "settings_subscription_pending": (
            "📊 Premium: kutilmoqda\n"
            "💳 To'lov jarayonda\n"
            "📦 Tarif: {plan}"
        ),
        "settings_subscription_blocked": "🚫 Akkount bloklangan.",
        "settings_subscription_status": "📊 Obuna holati",
        "settings_subscription_inactive": "📊 Premium: yo'q\n🆓 Bepul savollar: {used}/{limit}",
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
        "help_message_failed": "❌ Xabar operatorga yetmadi. Telefon orqali bog'laning.",
        "help_message_no_admins": "❌ Operator hozircha sozlanmagan.",
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
            "Quyida tariflarni ko'ring va mosini tanlang."
        ),
        "subscribe_catalog_header": (
            "⭐ Deenify Premium\n\n"
            "✅ Cheksiz testlar\n"
            "✅ Barcha savollarga kirish\n"
            "✅ Yangi testlar qo'shilganda avtomatik ochiladi"
        ),
        "subscribe_catalog_yearly": (
            "📅 Yillik — {monthly_price} so'm/oy\n"
            "   {months} oy • {total_price} so'm jami"
        ),
        "subscribe_catalog_yearly_discount": (
            "📅 Yillik — {monthly_price} so'm/oy  ·  -{discount}%\n"
            "   {months} oy • {total_price} so'm jami"
        ),
        "subscribe_catalog_monthly": "📅 Oylik — {price} so'm/oy\n   Har oy alohida to'lov",
        "subscribe_catalog_footer": "👇 Tarifni tanlang:",
        "payment_success_lifetime": "Abadiy",
        "payment_success_notification": (
            "🎉 To'lov muvaffaqiyatli o'tdi!\n\n"
            "⭐ <b>{plan_name}</b> premium obuna faollashtirildi.\n"
            "🗓 Amal qilish muddati: <b>{until}</b>\n\n"
            "Endi barcha testlar va savollar siz uchun ochiq. "
            "Bilimingizni oshirishda davom eting! 📚"
        ),
        "subscribe_plan_button_monthly": "Oylik · {price} so'm/oy",
        "subscribe_plan_button_yearly": "Yillik · {total_price} so'm",
        "subscribe_plan_button_yearly_discount": "Yillik · {total_price} so'm · -{discount}%",
        "subscribe_plan_button": "{name} — {price} UZS",
        "subscribe_pay_link": "💳 {price} so'm to'lash",
        "subscribe_payment_ready_monthly": (
            "✅ {plan_name} tanlandi\n\n"
            "💰 To'lov: {total_price} so'm\n"
            "📆 1 oylik obuna\n\n"
            "To'lov tugmasini bosing — karta ma'lumotlarini sahifada kiritasiz.\n"
            "To'lovdan keyin obuna avtomatik faollashadi."
        ),
        "subscribe_payment_ready_yearly": (
            "✅ {plan_name} tanlandi\n\n"
            "💰 To'lov: {total_price} so'm\n"
            "📆 {months} oylik obuna · {monthly_price} so'm/oy\n\n"
            "To'lov tugmasini bosing — karta ma'lumotlarini sahifada kiritasiz.\n"
            "To'lovdan keyin obuna avtomatik faollashadi."
        ),
        "subscribe_payment_ready_yearly_discount": (
            "✅ {plan_name} tanlandi\n\n"
            "💰 To'lov: {total_price} so'm\n"
            "📆 {months} oylik obuna · {monthly_price} so'm/oy · -{discount}%\n\n"
            "To'lov tugmasini bosing — karta ma'lumotlarini sahifada kiritasiz.\n"
            "To'lovdan keyin obuna avtomatik faollashadi."
        ),
        "subscribe_payment_failed": "❌ To'lov havolasi yaratilmadi.",
        "subscribe_no_plans": "❌ Hozircha obuna tariflari mavjud emas.",
        "settings_invite_friends": "👥 Do'stlarni taklif qilish",
        "settings_cancel_subscription": "❌ Obunani bekor qilish",
        "buy_premium_button": "💎 Premium sotib olish",
        "buy_premium_already_active": "✅ Sizda Premium obuna allaqachon faol.",
        "referral_panel": (
            "👥 <b>Do'stlarni taklif qiling</b>\n\n"
            "Quyidagi havolangizni ulashing. Do'stingiz ro'yxatdan o'tib, "
            "birinchi obunani sotib olsa, sizga bonus premium kunlar beriladi:\n"
            "• Oylik obuna uchun — <b>{monthly}</b> kun\n"
            "• Yillik obuna uchun — <b>{yearly}</b> kun\n\n"
            "🔗 {link}\n\n"
            "📊 Taklif qilinganlar: <b>{invited}</b>\n"
            "✅ Obuna bo'lganlar: <b>{paid}</b>"
        ),
        "referral_reward_notification": (
            "🎁 Tabriklaymiz! {invited_name} sizning havolangiz orqali premium obuna oldi.\n"
            "Sizga <b>{days}</b> kun bonus premium qo'shildi. Rahmat! 🙌"
        ),
        "cancel_no_subscription": "ℹ️ Sizda faol obuna yo'q.",
        "cancel_done": (
            "✅ Avto-uzaytirish o'chirildi va karta uzildi.\n"
            "Premium <b>{until}</b> gacha amal qiladi."
        ),
        "cancel_done_no_premium": "✅ Avto-uzaytirish o'chirildi va karta uzildi.",
        "feedback_decline_button": "❌ Premium kerak emas",
        "feedback_intro": "Bizga yordam bering: nega obuna bo'lmadingiz?",
        "feedback_reason_expensive": "💰 Narxi qimmat", 
        "feedback_reason_not_now": "🕒 Hozir kerak emas",
        "feedback_reason_trust": "🔒 Ishonch / xavfsizlik",
        "feedback_reason_hard_payment": "💳 To'lov qiyin bo'ldi",
        "feedback_reason_other": "✍️ Boshqa sabab",
        "feedback_skip": "O'tkazib yuborish",
        "feedback_other_prompt": "Iltimos, sababingizni yozib qoldiring:",
        "feedback_thanks": "🙏 Fikringiz uchun rahmat!",
        "subscription_renewal_failed": (
            "⚠️ Obunani avtomatik uzaytirib bo'lmadi (kartadan to'lov o'tmadi).\n"
            "Premiumni davom ettirish uchun qaytadan obuna bo'ling."
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
        "settings_subscription_active": (
            "📊 {plan}\n"
            "✅ Premium фaol\n"
            "📅 Бoshlandi: {starts}\n"
            "📅 Тugaydi: {until}"
        ),
        "settings_subscription_free": "📊 Premium: йўқ\n🆓 Бepul savollar: {used}/{limit}",
        "settings_subscription_free_exhausted": (
            "📊 Premium: йўқ\n"
            "🚫 Бepul limit tugadi ({used}/{limit})\n"
            "💎 Дavom etish uchun obuna kerak"
        ),
        "settings_subscription_expired": (
            "📊 {plan}\n"
            "⏰ Premium muddati tugagan\n"
            "📅 Tugagan sana: {until}\n"
            "🆓 Бepul savollar: {used}/{limit}"
        ),
        "settings_subscription_pending": (
            "📊 Premium: kutilmoqda\n"
            "💳 To'lov jarayonda\n"
            "📦 Tarif: {plan}"
        ),
        "settings_subscription_blocked": "🚫 Аккаунт блокланган.",
        "settings_subscription_status": "📊 Обuna holati",
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
        "help_message_failed": "❌ Хabar операторга yetmadi. Телефон орқали bog'laning.",
        "help_message_no_admins": "❌ Оператор ҳозирча созланмаган.",
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
            "Қуйида тарифни танланг ва тўловни амалга оширинг."
        ),
        "subscribe_catalog_header": (
            "⭐ Deenify Premium\n\n"
            "✅ Чексиз тестлар\n"
            "✅ Барча саволларга кириш\n"
            "✅ Янги тестлар қўшилади"
        ),
        "subscribe_catalog_yearly": (
            "📅 Йиллик — {monthly_price} so'm/ой\n"
            "   {months} ой • {total_price} so'm жами"
        ),
        "subscribe_catalog_yearly_discount": (
            "📅 Йиллик — {monthly_price} so'm/ой  ·  -{discount}%\n"
            "   {months} ой • {total_price} so'm жами"
        ),
        "subscribe_catalog_monthly": "📅 Ойлик — {price} so'm/ой\n   Ҳар ой алоҳида тўлов",
        "subscribe_catalog_footer": "👇 Тарифни танланг:",
        "payment_success_lifetime": "Абадий",
        "payment_success_notification": (
            "🎉 Тўлов муваффақиятли ўтди!\n\n"
            "⭐ <b>{plan_name}</b> премиум обуна фаоллаштирилди.\n"
            "🗓 Амал қилиш муддати: <b>{until}</b>\n\n"
            "Энди барча тестлар ва саволлар сиз учун очиқ. "
            "Билимингизни оширишда давом этинг! 📚"
        ),
        "subscribe_plan_button_monthly": "Ойлик · {price} so'm/ой",
        "subscribe_plan_button_yearly": "Йиллик · {total_price} so'm",
        "subscribe_plan_button_yearly_discount": "Йиллик · {total_price} so'm · -{discount}%",
        "subscribe_plan_button": "{name} — {price} UZS",
        "subscribe_pay_link": "💳 {price} so'm тўлаш",
        "subscribe_payment_ready_monthly": (
            "✅ {plan_name} танланди\n\n"
            "💰 Тўлов: {total_price} so'm\n"
            "📆 1 ойлик обуна\n\n"
            "Тўлов тугмасини босинг — карта маълумотларини саҳифада киритасиз.\n"
            "Тўловдан кейин обуна автоматик фаоллашади."
        ),
        "subscribe_payment_ready_yearly": (
            "✅ {plan_name} танланди\n\n"
            "💰 Тўлов: {total_price} so'm\n"
            "📆 {months} ойлик обуна · {monthly_price} so'm/ой\n\n"
            "Тўлов тугмасини босинг — карта маълумотларини саҳифада киритасиз.\n"
            "Тўловдан кейин обуна автоматик фаоллашади."
        ),
        "subscribe_payment_ready_yearly_discount": (
            "✅ {plan_name} танланди\n\n"
            "💰 Тўлов: {total_price} so'm\n"
            "📆 {months} ойлик обуна · {monthly_price} so'm/ой · -{discount}%\n\n"
            "Тўлов тугмасини босинг — карта маълумотларини саҳифада киритасиз.\n"
            "Тўловдан кейин обуна автоматик фаоллашади."
        ),
        "subscribe_payment_failed": "❌ Тўлов ҳаволаси яратилмади.",
        "subscribe_no_plans": "❌ Ҳозирча обуна тарифлари мавжуд эмас.",
        "settings_invite_friends": "👥 Дўстларни таклиф қилиш",
        "settings_cancel_subscription": "❌ Обунани бекор қилиш",
        "buy_premium_button": "💎 Premium сотиб олиш",
        "buy_premium_already_active": "✅ Сизда Premium обуна аллақачон фаол.",
        "referral_panel": (
            "👥 <b>Дўстларни таклиф қилинг</b>\n\n"
            "Қуйидаги ҳаволангизни улашинг. Дўстингиз рўйхатдан ўтиб, "
            "биринчи обунани сотиб олса, сизга бонус премиум кунлар берилади:\n"
            "• Ойлик обуна учун — <b>{monthly}</b> кун\n"
            "• Йиллик обуна учун — <b>{yearly}</b> кун\n\n"
            "🔗 {link}\n\n"
            "📊 Таклиф қилинганлар: <b>{invited}</b>\n"
            "✅ Обуна бўлганлар: <b>{paid}</b>"
        ),
        "referral_reward_notification": (
            "🎁 Табриклаймиз! {invited_name} сизнинг ҳаволангиз орқали премиум обуна олди.\n"
            "Сизга <b>{days}</b> кун бонус премиум қўшилди. Раҳмат! 🙌"
        ),
        "cancel_no_subscription": "ℹ️ Сизда фаол обуна йўқ.",
        "cancel_done": (
            "✅ Авто-узайтириш ўчирилди ва карта узилди.\n"
            "Премиум <b>{until}</b> гача амал қилади."
        ),
        "cancel_done_no_premium": "✅ Авто-узайтириш ўчирилди ва карта узилди.",
        "feedback_decline_button": "❌ Премиум керак эмас",
        "feedback_intro": "Бизга ёрдам беринг: нега обуна бўлмадингиз?",
        "feedback_reason_expensive": "💰 Нархи қиммат",
        "feedback_reason_not_now": "🕒 Ҳозир керак эмас",
        "feedback_reason_trust": "🔒 Ишонч / хавфсизлик",
        "feedback_reason_hard_payment": "💳 Тўлов қийин бўлди",
        "feedback_reason_other": "✍️ Бошқа сабаб",
        "feedback_skip": "Ўтказиб юбориш",
        "feedback_other_prompt": "Илтимос, сабабингизни ёзиб қолдиринг:",
        "feedback_thanks": "🙏 Фикрингиз учун раҳмат!",
        "subscription_renewal_failed": (
            "⚠️ Обунани автоматик узайтириб бўлмади (картадан тўлов ўтмади).\n"
            "Премиумни давом эттириш учун қайтадан обуна бўлинг."
        ),
        "quiz_restart_hint": "✨ Тест қайта бошланди. Барча саволлар бошидан, тасодифий тартибда.",
        "quiz_session_expired": (
            "⏳ Бу savolning muddati tugadi (bot qayta ishga tushgan bo'lishi mumkin).\n"
            "«Тест ечиш» tugmasini босинг."
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
        "settings_subscription_active": (
            "📊 {plan}\n"
            "✅ Premium активен\n"
            "📅 Начало: {starts}\n"
            "📅 Окончание: {until}"
        ),
        "settings_subscription_free": "📊 Premium: нет\n🆓 Бесплатные вопросы: {used}/{limit}",
        "settings_subscription_free_exhausted": (
            "📊 Premium: нет\n"
            "🚫 Бесплатный лимит исчерпан ({used}/{limit})\n"
            "💎 Для продолжения нужна подписка"
        ),
        "settings_subscription_expired": (
            "📊 {plan}\n"
            "⏰ Срок Premium истёк\n"
            "📅 Дата окончания: {until}\n"
            "🆓 Бесплатные вопросы: {used}/{limit}"
        ),
        "settings_subscription_pending": (
            "📊 Premium: ожидается\n"
            "💳 Платёж в обработке\n"
            "📦 Тариф: {plan}"
        ),
        "settings_subscription_blocked": "🚫 Аккаунт заблокирован.",
        "settings_subscription_status": "📊 Статус подписки",
        "settings_subscription_inactive": "📊 Premium: нет\n🆓 Бесплатные вопросы: {used}/{limit}",
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
        "help_message_failed": "❌ Сообщение не доставлено оператору. Позвоните по телефону.",
        "help_message_no_admins": "❌ Оператор пока не настроен.",
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
            "Выберите тариф ниже и оплатите."
        ),
        "subscribe_catalog_header": (
            "⭐ Deenify Premium\n\n"
            "✅ Безлимитные тесты\n"
            "✅ Доступ ко всем вопросам\n"
            "✅ Новые тесты открываются автоматически"
        ),
        "subscribe_catalog_yearly": (
            "📅 Годовой — {monthly_price} сум/мес\n"
            "   {months} мес. • {total_price} сум итого"
        ),
        "subscribe_catalog_yearly_discount": (
            "📅 Годовой — {monthly_price} сум/мес  ·  -{discount}%\n"
            "   {months} мес. • {total_price} сум итого"
        ),
        "subscribe_catalog_monthly": "📅 Месячный — {price} сум/мес\n   Оплата каждый месяц",
        "subscribe_catalog_footer": "👇 Выберите тариф:",
        "payment_success_lifetime": "Бессрочно",
        "payment_success_notification": (
            "🎉 Оплата прошла успешно!\n\n"
            "⭐ Премиум-подписка <b>{plan_name}</b> активирована.\n"
            "🗓 Действует до: <b>{until}</b>\n\n"
            "Теперь все тесты и вопросы открыты для вас. "
            "Продолжайте развиваться! 📚"
        ),
        "subscribe_plan_button_monthly": "Месяц · {price} сум/мес",
        "subscribe_plan_button_yearly": "Год · {total_price} сум",
        "subscribe_plan_button_yearly_discount": "Год · {total_price} сум · -{discount}%",
        "subscribe_plan_button": "{name} — {price} UZS",
        "subscribe_pay_link": "💳 Оплатить {price} сум",
        "subscribe_payment_ready_monthly": (
            "✅ Выбран: {plan_name}\n\n"
            "💰 К оплате: {total_price} сум\n"
            "📆 Подписка на 1 месяц\n\n"
            "Нажмите кнопку оплаты — введите карту на странице.\n"
            "После оплаты подписка активируется автоматически."
        ),
        "subscribe_payment_ready_yearly": (
            "✅ Выбран: {plan_name}\n\n"
            "💰 К оплате: {total_price} сум\n"
            "📆 Подписка на {months} мес. · {monthly_price} сум/мес\n\n"
            "Нажмите кнопку оплаты — введите карту на странице.\n"
            "После оплаты подписка активируется автоматически."
        ),
        "subscribe_payment_ready_yearly_discount": (
            "✅ Выбран: {plan_name}\n\n"
            "💰 К оплате: {total_price} сум\n"
            "📆 Подписка на {months} мес. · {monthly_price} сум/мес · -{discount}%\n\n"
            "Нажмите кнопку оплаты — введите карту на странице.\n"
            "После оплаты подписка активируется автоматически."
        ),
        "subscribe_payment_failed": "❌ Не удалось создать ссылку на оплату.",
        "subscribe_no_plans": "❌ Тарифы подписки пока недоступны.",
        "settings_invite_friends": "👥 Пригласить друзей",
        "settings_cancel_subscription": "❌ Отменить подписку",
        "buy_premium_button": "💎 Купить премиум",
        "buy_premium_already_active": "✅ У вас уже активна Premium-подписка.",
        "referral_panel": (
            "👥 <b>Пригласите друзей</b>\n\n"
            "Поделитесь своей ссылкой. Когда друг зарегистрируется и оформит "
            "первую подписку, вы получите бонусные дни премиума:\n"
            "• За месячную подписку — <b>{monthly}</b> дн.\n"
            "• За годовую подписку — <b>{yearly}</b> дн.\n\n"
            "🔗 {link}\n\n"
            "📊 Приглашено: <b>{invited}</b>\n"
            "✅ Оформили подписку: <b>{paid}</b>"
        ),
        "referral_reward_notification": (
            "🎁 Поздравляем! {invited_name} оформил премиум-подписку по вашей ссылке.\n"
            "Вам добавлено <b>{days}</b> дн. бонусного премиума. Спасибо! 🙌"
        ),
        "cancel_no_subscription": "ℹ️ У вас нет активной подписки.",
        "cancel_done": (
            "✅ Автопродление отключено, карта отвязана.\n"
            "Премиум действует до <b>{until}</b>."
        ),
        "cancel_done_no_premium": "✅ Автопродление отключено, карта отвязана.",
        "feedback_decline_button": "❌ Премиум не нужен",
        "feedback_intro": "Помогите нам: почему вы не оформили подписку?",
        "feedback_reason_expensive": "💰 Дорого",
        "feedback_reason_not_now": "🕒 Сейчас не нужно",
        "feedback_reason_trust": "🔒 Доверие / безопасность",
        "feedback_reason_hard_payment": "💳 Сложно оплатить",
        "feedback_reason_other": "✍️ Другая причина",
        "feedback_skip": "Пропустить",
        "feedback_other_prompt": "Пожалуйста, напишите вашу причину:",
        "feedback_thanks": "🙏 Спасибо за ваш отзыв!",
        "subscription_renewal_failed": (
            "⚠️ Не удалось автоматически продлить подписку (оплата картой не прошла).\n"
            "Чтобы продолжить премиум, оформите подписку заново."
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
