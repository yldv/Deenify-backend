import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from bot.api_client import ApiClientError
from bot.handlers.common import show_home_menu, user_full_name
from bot.keyboards import phone_keyboard
from bot.states import RegistrationState
from bot.texts import get_text, normalize_language

router = Router()
logger = logging.getLogger(__name__)


@router.message(RegistrationState.waiting_for_phone, F.contact)
async def phone_received(message: Message, state: FSMContext, api_client):
    data = await state.get_data()
    language = normalize_language(data.get("language", "uz"))

    try:
        await api_client.get_or_create_user(
            telegram_id=message.from_user.id,
            full_name=user_full_name(message),
            username=message.from_user.username or "",
            language=language,
            phone_number=message.contact.phone_number,
        )
    except ApiClientError as exc:
        logger.exception(
            "Phone registration failed: method=%s url=%s status=%s response=%s",
            exc.method,
            exc.url,
            exc.status,
            exc.response_text,
        )
        await message.answer(get_text(language, "error"), reply_markup=phone_keyboard(language))
        return

    await state.clear()
    await message.answer(get_text(language, "registration_success"))
    await show_home_menu(message, language)


@router.message(RegistrationState.waiting_for_phone)
async def invalid_phone(message: Message, state: FSMContext):
    data = await state.get_data()
    language = normalize_language(data.get("language", "uz"))
    await message.answer(
        get_text(language, "phone_invalid"),
        reply_markup=phone_keyboard(language),
    )
