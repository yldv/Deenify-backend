from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from bot.config import BotConfig
from bot.context import get_language, preserve_language
from bot.handlers.start import show_home_menu
from bot.keyboards import cancel_keyboard, help_keyboard, home_keyboard
from bot.states import HelpState
from bot.texts import all_button_texts, get_text

router = Router()


@router.message(F.text.in_(all_button_texts("help")))
async def open_help(message: Message, state: FSMContext):
    language = await get_language(state)
    await state.set_state(HelpState.menu)
    await message.answer(
        get_text(language, "help_intro"),
        reply_markup=help_keyboard(language),
    )


@router.message(HelpState.menu, F.text.in_(all_button_texts("help_phone")))
async def help_phone(message: Message, state: FSMContext, bot_config: BotConfig):
    language = await get_language(state)
    if bot_config.support_phone:
        await message.answer(
            get_text(language, "help_phone_number", phone=bot_config.support_phone),
            reply_markup=help_keyboard(language),
        )
        return
    await message.answer(
        get_text(language, "help_phone_missing"),
        reply_markup=help_keyboard(language),
    )


@router.message(HelpState.menu, F.text.in_(all_button_texts("help_message")))
async def help_message_start(message: Message, state: FSMContext):
    language = await get_language(state)
    await state.set_state(HelpState.waiting_for_message)
    await message.answer(
        get_text(language, "help_message_prompt"),
        reply_markup=cancel_keyboard(language),
    )


@router.message(HelpState.waiting_for_message, F.text.in_(all_button_texts("help_cancel")))
async def help_message_cancel(message: Message, state: FSMContext):
    language = await preserve_language(state)
    await state.set_state(HelpState.menu)
    await message.answer(
        get_text(language, "help_intro"),
        reply_markup=help_keyboard(language),
    )


@router.message(HelpState.waiting_for_message)
async def help_message_received(
    message: Message,
    state: FSMContext,
    bot: Bot,
    bot_config: BotConfig,
):
    language = await get_language(state)
    text = (message.text or "").strip()
    if not text:
        await message.answer(
            get_text(language, "help_message_empty"),
            reply_markup=cancel_keyboard(language),
        )
        return

    user = message.from_user
    admin_text = (
        f"📬 Help message\n"
        f"From: {user.full_name} (@{user.username or '—'})\n"
        f"ID: {user.id}\n\n"
        f"{text}"
    )
    for admin_id in bot_config.admin_ids:
        try:
            await bot.send_message(admin_id, admin_text)
        except Exception:
            continue

    await preserve_language(state)
    await state.set_state(HelpState.menu)
    await message.answer(
        get_text(language, "help_message_sent"),
        reply_markup=help_keyboard(language),
    )


@router.message(HelpState.menu, F.text.in_(all_button_texts("back")))
async def help_back(message: Message, state: FSMContext):
    language = await preserve_language(state)
    await show_home_menu(message, language)
