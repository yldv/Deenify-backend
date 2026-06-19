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


def _home_keyboard_rows(language: str, is_premium: bool):
    second_row = []
    if not is_premium:
        second_row.append(get_text(language, "buy_premium_button"))
    second_row.append(get_text(language, "settings_invite_friends"))
    return [
        [get_text(language, "take_test"), get_text(language, "restart_from_start")],
        second_row,
        [get_text(language, "settings")],
    ]


def home_keyboard_reply_dict(language: str, is_premium: bool = False) -> dict:
    """Telegram sendMessage reply_markup dict (bot + backend notifications)."""
    rows = _home_keyboard_rows(language, is_premium)
    return {
        "keyboard": [[{"text": label} for label in row] for row in rows],
        "resize_keyboard": True,
        "is_persistent": True,
    }


def home_keyboard(language: str, is_premium: bool = False):
    # "Buy premium" only makes sense for users without an active subscription.
    rows = _home_keyboard_rows(language, is_premium)
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=label) for label in row] for row in rows
        ],
        resize_keyboard=True,
        is_persistent=True,
    )


def settings_keyboard(language: str, is_premium: bool = False):
    # "Cancel subscription" only makes sense for users who actually have premium.
    first_row = [KeyboardButton(text=get_text(language, "settings_subscription_status"))]
    if is_premium:
        first_row.append(
            KeyboardButton(text=get_text(language, "settings_cancel_subscription"))
        )
    return ReplyKeyboardMarkup(
        keyboard=[
            first_row,
            [
                KeyboardButton(text=get_text(language, "help")),
                KeyboardButton(text=get_text(language, "change_language")),
            ],
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
