import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from bot.context import get_language
from bot.services.payment import (
    PAY_CONFIRM_PREFIX,
    PLAN_CALLBACK_PREFIX,
    resolve_payment_url,
    send_plan_payment_prompt,
)
from bot.texts import get_text

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
    await send_plan_payment_prompt(
        message=callback.message,
        language=language,
        plan_id=int(plan_id_raw),
    )


@router.callback_query(F.data.startswith(PAY_CONFIRM_PREFIX))
async def pay_confirm(callback: CallbackQuery, state: FSMContext, api_client):
    if not callback.from_user or not callback.message:
        await callback.answer()
        return

    plan_id_raw = callback.data.removeprefix(PAY_CONFIRM_PREFIX)
    if not plan_id_raw.isdigit():
        await callback.answer()
        return

    language = await get_language(state)
    payment_url, payment_error = await resolve_payment_url(
        api_client=api_client,
        telegram_id=callback.from_user.id,
        plan_id=int(plan_id_raw),
    )
    if not payment_url:
        error_text = get_text(language, "subscribe_payment_failed")
        if payment_error:
            error_text = f"{error_text}\n{payment_error}"
        await callback.answer(error_text, show_alert=True)
        return

    await callback.answer(url=payment_url)
