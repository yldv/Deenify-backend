from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.api_client import ApiClientError, BlockedUserError, NotFoundError
from bot.keyboards import payment_keyboard, plans_keyboard
from bot.texts import get_text, normalize_language

router = Router()


async def get_language(state: FSMContext) -> str:
    data = await state.get_data()
    return normalize_language(data.get("language", "uz"))


@router.message(F.text.in_([
    get_text("uz", "buy_premium"),
    get_text("ru", "buy_premium"),
    get_text("en", "buy_premium"),
]))
async def premium_button(message: Message, state: FSMContext, api_client):
    language = await get_language(state)
    try:
        plans = await api_client.get_subscription_plans(language=language)
    except ApiClientError:
        await message.answer(get_text(language, "error"))
        return

    if not plans:
        await message.answer(get_text(language, "not_found"))
        return
    await message.answer(get_text(language, "plans"), reply_markup=plans_keyboard(plans))


@router.callback_query(F.data.startswith("plan:"))
async def plan_selected(callback: CallbackQuery, state: FSMContext, api_client):
    language = await get_language(state)
    plan_id = int(callback.data.split(":", 1)[1])
    try:
        order = await api_client.create_atmos_order(
            telegram_id=callback.from_user.id,
            plan_id=plan_id,
        )
    except BlockedUserError:
        await callback.message.answer(get_text(language, "blocked"))
        await callback.answer()
        return
    except NotFoundError:
        await callback.message.answer(get_text(language, "not_found"))
        await callback.answer()
        return
    except ApiClientError:
        await callback.message.answer(get_text(language, "error"))
        await callback.answer()
        return

    await callback.message.answer(
        get_text(language, "payment_text"),
        reply_markup=payment_keyboard(order.get("payment_url", ""), language),
    )
    await callback.answer()


@router.callback_query(F.data == "check_premium")
async def check_premium(callback: CallbackQuery, state: FSMContext, api_client):
    language = await get_language(state)
    try:
        stats = await api_client.get_statistics(telegram_id=callback.from_user.id)
    except ApiClientError:
        await callback.message.answer(get_text(language, "error"))
        await callback.answer()
        return

    text = get_text(language, "premium_active") if stats.get("is_premium") else get_text(language, "premium_inactive")
    await callback.message.answer(text)
    await callback.answer()
