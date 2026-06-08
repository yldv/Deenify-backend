from aiogram.types import Message

from bot.keyboards import home_keyboard
from bot.texts import get_text


def user_full_name(message: Message) -> str:
    parts = [message.from_user.first_name or "", message.from_user.last_name or ""]
    return " ".join(part for part in parts if part).strip()


async def show_home_menu(message: Message, language: str):
    await message.answer(
        get_text(language, "home_menu"),
        reply_markup=home_keyboard(language),
    )
