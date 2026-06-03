from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup

from .texts import (
    LANGUAGE_BUTTON_TEXTS,
    get_text,
)


def language_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=label)] for label in LANGUAGE_BUTTON_TEXTS],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def phone_keyboard(language: str):
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=get_text(language, "share_phone"), request_contact=True)],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def home_keyboard(language: str):
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text=get_text(language, "take_test")),
                KeyboardButton(text=get_text(language, "restart_from_start")),
            ],
            [
                KeyboardButton(text=get_text(language, "help")),
                KeyboardButton(text=get_text(language, "settings")),
            ],
        ],
        resize_keyboard=True,
        is_persistent=True,
    )


INLINE_BUTTON_TEXT_LIMIT = 64


def quiz_answers_keyboard(question_id: int, answers: list[dict]) -> InlineKeyboardMarkup:
    keyboard = []
    for answer in answers:
        text = (answer.get("text") or "").strip()
        if len(text) > INLINE_BUTTON_TEXT_LIMIT:
            text = text[: INLINE_BUTTON_TEXT_LIMIT - 1] + "…"
        keyboard.append(
            [
                InlineKeyboardButton(
                    text=text,
                    callback_data=f"quiz:{question_id}:{answer['id']}",
                )
            ]
        )
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def settings_keyboard(language: str):
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=get_text(language, "change_language"))],
            [KeyboardButton(text=get_text(language, "back"))],
        ],
        resize_keyboard=True,
        is_persistent=True,
    )


def help_keyboard(language: str):
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=get_text(language, "help_phone"))],
            [KeyboardButton(text=get_text(language, "help_message"))],
            [KeyboardButton(text=get_text(language, "back"))],
        ],
        resize_keyboard=True,
        is_persistent=True,
    )


def cancel_keyboard(language: str):
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=get_text(language, "help_cancel"))]],
        resize_keyboard=True,
        is_persistent=True,
    )
