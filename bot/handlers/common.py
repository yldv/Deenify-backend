from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from bot.api_client import ApiClientError, NotFoundError
from bot.context import get_language
from bot.keyboards import home_keyboard, phone_keyboard
from bot.states import RegistrationState
from bot.texts import get_text, normalize_language


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


async def prompt_phone_registration(
    message: Message,
    state: FSMContext,
    *,
    language: str | None = None,
) -> None:
    language = normalize_language(language or await get_language(state))
    await state.set_state(RegistrationState.waiting_for_phone)
    await state.update_data(language=language)
    await message.answer(
        get_text(language, "phone_prompt"),
        reply_markup=phone_keyboard(language),
    )


async def require_registered_user(
    message: Message,
    state: FSMContext,
    api_client,
    *,
    telegram_id: int | None = None,
) -> tuple[dict, str] | None:
    """Return (backend_user, language) or prompt for phone and return None."""
    telegram_id = telegram_id or message.from_user.id
    try:
        user = await api_client.get_user(telegram_id=telegram_id)
    except NotFoundError:
        language = await get_language(state)
        await prompt_phone_registration(message, state, language=language)
        return None
    except ApiClientError:
        language = await get_language(state)
        await message.answer(get_text(language, "error"))
        return None

    language = normalize_language(user.get("language") or await get_language(state))
    if user.get("is_registered"):
        return user, language

    await prompt_phone_registration(message, state, language=language)
    return None
