from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

from .texts import (
    LANGUAGE_BUTTON_TEXTS,
    get_text,
)

FEEDBACK_DECLINE_PREFIX = "fb_decline:"
FEEDBACK_REASON_PREFIX = "fb_reason:"
FEEDBACK_SKIP_PREFIX = "fb_skip:"
FEEDBACK_REASONS = ("expensive", "not_now", "trust", "hard_payment", "other")


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
            [KeyboardButton(text=get_text(language, "settings_invite_friends"))],
            [KeyboardButton(text=get_text(language, "settings_cancel_subscription"))],
            [KeyboardButton(text=get_text(language, "change_language"))],
            [KeyboardButton(text=get_text(language, "back"))],
        ],
        resize_keyboard=True,
        is_persistent=True,
    )


def feedback_decline_button(language: str, context: str = "declined") -> InlineKeyboardButton:
    return InlineKeyboardButton(
        text=get_text(language, "feedback_decline_button"),
        callback_data=f"{FEEDBACK_DECLINE_PREFIX}{context}",
    )


def feedback_reasons_keyboard(language: str, context: str) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text=get_text(language, f"feedback_reason_{reason}"),
                callback_data=f"{FEEDBACK_REASON_PREFIX}{context}:{reason}",
            )
        ]
        for reason in FEEDBACK_REASONS
    ]
    rows.append(
        [
            InlineKeyboardButton(
                text=get_text(language, "feedback_skip"),
                callback_data=f"{FEEDBACK_SKIP_PREFIX}{context}",
            )
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


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
