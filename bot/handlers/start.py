import logging

from aiogram import F, Router
from aiogram.filters import CommandObject, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.api_client import ApiClientError, NotFoundError
from bot.handlers.common import show_home_menu, user_full_name
from bot.handlers.settings import show_settings_menu
from bot.keyboards import home_keyboard, language_keyboard, phone_keyboard
from bot.states import ChoosingLanguage, RegistrationState
from bot.texts import (
    LANGUAGE_BUTTON_TEXTS,
    LANGUAGE_BUTTON_TO_CODE_UI,
    get_text,
    normalize_language,
)

router = Router()
logger = logging.getLogger(__name__)


def _parse_referrer_id(command: CommandObject | None, telegram_id: int):
    """Extract the inviter id from a /start ref_<id> deep link (never self)."""
    if not command or not command.args:
        return None
    args = command.args.strip()
    if not args.startswith("ref_"):
        return None
    raw = args[len("ref_"):]
    if not raw.isdigit():
        return None
    referrer_id = int(raw)
    return referrer_id if referrer_id != telegram_id else None


@router.message(CommandStart())
async def start_command(
    message: Message,
    state: FSMContext,
    api_client,
    command: CommandObject | None = None,
):
    referrer_id = _parse_referrer_id(command, message.from_user.id)
    try:
        user = await api_client.get_user(telegram_id=message.from_user.id)
    except NotFoundError:
        user = None
    except ApiClientError:
        await message.answer(get_text("uz", "error"))
        return

    if user and user.get("is_registered"):
        language = normalize_language(user.get("language", "uz"))
        await state.update_data(language=language)
        await state.clear()
        await show_home_menu(message, language)
        return

    await state.set_state(ChoosingLanguage.language)
    if referrer_id:
        await state.update_data(referrer_id=referrer_id)
    await message.answer(
        get_text("uz", "choose_language"),
        reply_markup=language_keyboard(),
    )


@router.message(ChoosingLanguage.language, F.text.in_(LANGUAGE_BUTTON_TEXTS))
async def language_selected(message: Message, state: FSMContext, api_client):
    language = normalize_language(LANGUAGE_BUTTON_TO_CODE_UI[message.text])
    telegram_id = message.from_user.id
    data = await state.get_data()
    is_changing = bool(data.get("language"))

    try:
        if is_changing:
            user = await api_client.change_language(telegram_id=telegram_id, language=language)
            language = normalize_language(user.get("language", language))
            await state.update_data(language=language)
            return_to = data.get("return_to")
            await state.update_data(return_to=None)
            await message.answer(get_text(language, "language_updated"))
            if return_to == "settings":
                await show_settings_menu(message, state, language)
            else:
                await state.clear()
                await show_home_menu(message, language)
        else:
            await api_client.get_or_create_user(
                telegram_id=telegram_id,
                full_name=user_full_name(message),
                username=message.from_user.username or "",
                language=language,
                referred_by=data.get("referrer_id"),
            )
            await state.update_data(language=language, referrer_id=None)
            await state.set_state(RegistrationState.waiting_for_phone)
            await message.answer(
                get_text(language, "phone_prompt"),
                reply_markup=phone_keyboard(language),
            )
    except ApiClientError as exc:
        logger.exception(
            "Language selection API request failed: method=%s url=%s status=%s response=%s",
            exc.method,
            exc.url,
            exc.status,
            exc.response_text,
        )
        await message.answer(get_text(language, "error"), reply_markup=language_keyboard())


@router.message(ChoosingLanguage.language)
async def invalid_language(message: Message, state: FSMContext):
    data = await state.get_data()
    language = normalize_language(data.get("language", "uz"))
    await message.answer(
        get_text(language, "choose_language_button_hint"),
        reply_markup=language_keyboard(),
    )


@router.callback_query(F.data == "back_menu")
async def back_to_menu(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    language = normalize_language(data.get("language", "uz"))
    await callback.message.answer(
        get_text(language, "home_menu"),
        reply_markup=home_keyboard(language),
    )
    await callback.answer()
