from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from bot.context import preserve_language
from bot.handlers.help import open_help
from bot.handlers.settings import open_settings
from bot.handlers.common import require_registered_user, resolve_is_premium, show_home_menu
router = Router()


@router.message(Command("menu"))
async def cmd_menu(message: Message, state: FSMContext, api_client):
    registered = await require_registered_user(message, state, api_client)
    if not registered:
        return
    _, language = registered
    await preserve_language(state, language)
    is_premium = await resolve_is_premium(api_client, message.from_user.id)
    await show_home_menu(message, language, is_premium=is_premium)


@router.message(Command("help"))
async def cmd_help(message: Message, state: FSMContext, api_client):
    await open_help(message, state, api_client)


@router.message(Command("settings"))
async def cmd_settings(message: Message, state: FSMContext, api_client):
    await open_settings(message, state, api_client)
