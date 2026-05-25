from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from bot.context import get_language, preserve_language
from bot.handlers.start import show_home_menu
from bot.keyboards import language_keyboard, settings_keyboard
from bot.states import ChoosingLanguage, SettingsState
from bot.texts import all_button_texts, get_text

router = Router()


@router.message(F.text.in_(all_button_texts("settings")))
async def open_settings(message: Message, state: FSMContext):
    language = await get_language(state)
    await state.set_state(SettingsState.menu)
    await message.answer(
        get_text(language, "settings_section"),
        reply_markup=settings_keyboard(language),
    )


@router.message(SettingsState.menu, F.text.in_(all_button_texts("change_language")))
async def settings_change_language(message: Message, state: FSMContext):
    language = await get_language(state)
    await state.set_state(ChoosingLanguage.language)
    await message.answer(
        get_text(language, "choose_language"),
        reply_markup=language_keyboard(),
    )


@router.message(SettingsState.menu, F.text.in_(all_button_texts("back")))
async def settings_back(message: Message, state: FSMContext):
    language = await preserve_language(state)
    await show_home_menu(message, language)
