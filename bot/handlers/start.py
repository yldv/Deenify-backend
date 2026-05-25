import logging

from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.api_client import ApiClientError, NotFoundError
from bot.keyboards import home_keyboard, language_keyboard, phone_keyboard
from bot.states import ChoosingLanguage, RegistrationState
from bot.texts import (
    LANGUAGE_BUTTON_TEXTS,
    LANGUAGE_BUTTON_TO_CODE_UI,
    all_button_texts,
    get_text,
    normalize_language,
)

router = Router()
logger = logging.getLogger(__name__)


def user_full_name(message: Message) -> str:
    parts = [message.from_user.first_name or "", message.from_user.last_name or ""]
    return " ".join(part for part in parts if part).strip()


async def show_home_menu(message: Message, language: str):
    await message.answer(
        get_text(language, "home_menu"),
        reply_markup=home_keyboard(language),
    )


@router.message(CommandStart())
async def start_command(message: Message, state: FSMContext, api_client):
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
    await message.answer(
        get_text("uz", "choose_language"),
        reply_markup=language_keyboard(),
    )


@router.message(F.text.in_(all_button_texts("change_language")))
async def change_language_button(message: Message, state: FSMContext):
    data = await state.get_data()
    language = normalize_language(data.get("language", "uz"))
    await state.set_state(ChoosingLanguage.language)
    await message.answer(
        get_text(language, "choose_language"),
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
            await state.clear()
            await message.answer(get_text(language, "language_updated"))
            await show_home_menu(message, language)
        else:
            await api_client.get_or_create_user(
                telegram_id=telegram_id,
                full_name=user_full_name(message),
                username=message.from_user.username or "",
                language=language,
            )
            await state.update_data(language=language)
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
