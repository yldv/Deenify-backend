from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

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


def settings_keyboard(language: str):
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=get_text(language, "settings_subscription_status"))],
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
