from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from bot.context import preserve_language
from bot.handlers.help import open_help
from bot.handlers.settings import open_settings
from bot.handlers.start import show_home_menu
router = Router()


@router.message(Command("menu"))
async def cmd_menu(message: Message, state: FSMContext):
    language = await preserve_language(state)
    await show_home_menu(message, language)


@router.message(Command("help"))
async def cmd_help(message: Message, state: FSMContext):
    await open_help(message, state)


@router.message(Command("settings"))
async def cmd_settings(message: Message, state: FSMContext, api_client):
    await open_settings(message, state, api_client)
