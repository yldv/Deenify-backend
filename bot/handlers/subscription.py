import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from bot.context import get_language
from bot.services.payment import PLAN_CALLBACK_PREFIX, create_payment_link

router = Router()
logger = logging.getLogger(__name__)


@router.callback_query(F.data.startswith(PLAN_CALLBACK_PREFIX))
async def plan_selected(callback: CallbackQuery, state: FSMContext, api_client):
    if not callback.from_user or not callback.message:
        await callback.answer()
        return

    plan_id_raw = callback.data.removeprefix(PLAN_CALLBACK_PREFIX)
    if not plan_id_raw.isdigit():
        await callback.answer()
        return

    language = await get_language(state)
    await callback.answer()
    await create_payment_link(
        message=callback.message,
        language=language,
        api_client=api_client,
        telegram_id=callback.from_user.id,
        plan_id=int(plan_id_raw),
    )
