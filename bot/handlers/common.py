from aiogram.types import Message

from bot.keyboards import home_keyboard
from bot.texts import get_text


def user_full_name(message: Message) -> str:
    parts = [message.from_user.first_name or "", message.from_user.last_name or ""]
    return " ".join(part for part in parts if part).strip()


async def show_home_menu(message: Message, language: str, is_premium: bool = False):
    await message.answer(
        get_text(language, "home_menu"),
        reply_markup=home_keyboard(language, is_premium=is_premium),
    )


async def resolve_is_premium(api_client, telegram_id) -> bool:
    """Best-effort premium check used to tailor the reply keyboard. Never raises."""
    try:
        user = await api_client.get_user(telegram_id=telegram_id)
    except Exception:  # noqa: BLE001
        return False
    return bool(user.get("is_premium"))
