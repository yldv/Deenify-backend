import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from bot.api_client import ApiClientError, NotFoundError
from bot.context import get_language, preserve_language
from bot.handlers.start import show_home_menu
from bot.keyboards import home_keyboard, language_keyboard, settings_keyboard
from bot.services.subscription import build_subscription_summary
from bot.states import ChoosingLanguage, SettingsState
from bot.texts import all_button_texts, get_text

router = Router()
logger = logging.getLogger(__name__)


async def show_settings_menu(message: Message, state: FSMContext, language: str, user: dict | None = None):
    lines = [get_text(language, "settings_section")]
    if user:
        if user.get("is_blocked"):
            lines.append(get_text(language, "settings_subscription_blocked"))
        else:
            lines.append(build_subscription_summary(language=language, user=user))
    await state.set_state(SettingsState.menu)
    await message.answer(
        "\n\n".join(lines),
        reply_markup=settings_keyboard(language),
    )


@router.message(F.text.in_(all_button_texts("settings")))
async def open_settings(message: Message, state: FSMContext, api_client):
    language = await get_language(state)
    try:
        user = await api_client.get_user(telegram_id=message.from_user.id)
    except NotFoundError:
        user = None
    except ApiClientError:
        logger.exception("Failed to load user for settings telegram_id=%s", message.from_user.id)
        await message.answer(get_text(language, "error"))
        return

    await show_settings_menu(message, state, language, user)


@router.message(SettingsState.menu, F.text.in_(all_button_texts("settings_subscription_status")))
async def refresh_subscription_status(message: Message, state: FSMContext, api_client):
    language = await get_language(state)
    try:
        user = await api_client.get_user(telegram_id=message.from_user.id)
    except NotFoundError:
        await message.answer(get_text(language, "not_found"), reply_markup=home_keyboard(language))
        return
    except ApiClientError:
        logger.exception(
            "Failed to refresh subscription status telegram_id=%s",
            message.from_user.id,
        )
        await message.answer(get_text(language, "error"))
        return

    await show_settings_menu(message, state, language, user)


@router.message(SettingsState.menu, F.text.in_(all_button_texts("change_language")))
async def settings_change_language(message: Message, state: FSMContext):
    language = await get_language(state)
    await state.update_data(return_to="settings")
    await state.set_state(ChoosingLanguage.language)
    await message.answer(
        get_text(language, "choose_language"),
        reply_markup=language_keyboard(),
    )


@router.message(SettingsState.menu, F.text.in_(all_button_texts("back")))
async def settings_back(message: Message, state: FSMContext):
    language = await preserve_language(state)
    await show_home_menu(message, language)
