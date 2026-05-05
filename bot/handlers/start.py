import logging

from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.api_client import ApiClientError
from bot.keyboards import language_keyboard, main_menu_keyboard
from bot.states import ChoosingLanguage
from bot.texts import get_text, normalize_language

router = Router()
logger = logging.getLogger(__name__)


def user_full_name(message: Message) -> str:
    parts = [message.from_user.first_name or "", message.from_user.last_name or ""]
    return " ".join(part for part in parts if part).strip()


async def show_main_menu(message: Message, language: str):
    await message.answer(
        get_text(language, "main_menu"),
        reply_markup=main_menu_keyboard(language),
    )


@router.message(CommandStart())
async def start_command(message: Message, state: FSMContext):
    await state.set_state(ChoosingLanguage.language)
    await message.answer(get_text("uz", "choose_language"), reply_markup=language_keyboard())


@router.message(F.text.in_([
    get_text("uz", "change_language"),
    get_text("ru", "change_language"),
    get_text("en", "change_language"),
]))
async def change_language_button(message: Message, state: FSMContext):
    data = await state.get_data()
    language = normalize_language(data.get("language", "uz"))
    await state.set_state(ChoosingLanguage.language)
    await message.answer(get_text(language, "choose_language"), reply_markup=language_keyboard())


@router.callback_query(F.data.startswith("lang:"))
async def language_selected(callback: CallbackQuery, state: FSMContext, api_client):
    language = normalize_language(callback.data.split(":", 1)[1])
    telegram_id = callback.from_user.id

    try:
        data = await state.get_data()
        if data.get("language"):
            user = await api_client.change_language(telegram_id=telegram_id, language=language)
            text = get_text(language, "language_updated")
        else:
            user = await api_client.get_or_create_user(
                telegram_id=telegram_id,
                full_name=" ".join(
                    part for part in [callback.from_user.first_name, callback.from_user.last_name] if part
                ),
                username=callback.from_user.username,
                language=language,
            )
            text = get_text(language, "main_menu")
    except ApiClientError as exc:
        logger.exception(
            "Language selection API request failed: method=%s url=%s status=%s response=%s",
            exc.method,
            exc.url,
            exc.status,
            exc.response_text,
        )
        await callback.message.answer(get_text(language, "error"))
        await callback.answer()
        return

    language = normalize_language(user.get("language", language))
    await state.update_data(language=language)
    await callback.message.answer(text, reply_markup=main_menu_keyboard(language))
    await callback.answer()


@router.callback_query(F.data == "back_menu")
async def back_to_menu(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    language = normalize_language(data.get("language", "uz"))
    await callback.message.answer(
        get_text(language, "main_menu"),
        reply_markup=main_menu_keyboard(language),
    )
    await callback.answer()
