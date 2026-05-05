from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup

from .texts import get_text


LANGUAGE_BUTTONS = [
    ("🇺🇿 Uzbek", "lang:uz"),
    ("🇷🇺 Русский", "lang:ru"),
    ("🇬🇧 English", "lang:en"),
]


def language_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=text, callback_data=callback)]
            for text, callback in LANGUAGE_BUTTONS
        ]
    )


def main_menu_keyboard(language):
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text=get_text(language, "take_test")),
                KeyboardButton(text=get_text(language, "profile")),
            ],
            [
                KeyboardButton(text=get_text(language, "buy_premium")),
                KeyboardButton(text=get_text(language, "change_language")),
            ],
        ],
        resize_keyboard=True,
    )


def test_type_keyboard(language):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=get_text(language, "easy"), callback_data="test_type:easy"),
                InlineKeyboardButton(text=get_text(language, "medium"), callback_data="test_type:medium"),
            ],
            [
                InlineKeyboardButton(text=get_text(language, "hard"), callback_data="test_type:hard"),
                InlineKeyboardButton(text=get_text(language, "mixed"), callback_data="test_type:mixed"),
            ],
        ]
    )


def answers_keyboard(answers):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=answer["text"], callback_data=f"answer:{answer['id']}")]
            for answer in answers
        ]
    )


def plans_keyboard(plans):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"{plan['name']} - {plan['price']}",
                    callback_data=f"plan:{plan['id']}",
                )
            ]
            for plan in plans
        ]
    )


def payment_keyboard(payment_url, language):
    buttons = []
    if payment_url:
        buttons.append([InlineKeyboardButton(text=get_text(language, "pay"), url=payment_url)])
    buttons.append([InlineKeyboardButton(text=get_text(language, "check_premium"), callback_data="check_premium")])
    buttons.append([InlineKeyboardButton(text=get_text(language, "back_menu"), callback_data="back_menu")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def back_menu_keyboard(language):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=get_text(language, "back_menu"), callback_data="back_menu")]
        ]
    )
