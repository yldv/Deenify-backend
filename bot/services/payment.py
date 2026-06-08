import logging

from aiogram import Bot
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message

from bot.api_client import ApiClientError
from bot.texts import get_text

logger = logging.getLogger(__name__)

PLAN_CALLBACK_PREFIX = "pay_plan:"


def plan_button_label(language: str, plan: dict) -> str:
    price = plan.get("price")
    if isinstance(price, str):
        price = price.rstrip("0").rstrip(".") if "." in price else price
    return get_text(
        language,
        "subscribe_plan_button",
        name=plan.get("name", "Premium"),
        price=price,
    )


def build_plan_choice_keyboard(language: str, plans: list[dict]) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=plan_button_label(language, plan), callback_data=f"{PLAN_CALLBACK_PREFIX}{plan['id']}")]
        for plan in plans
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def build_payment_url_keyboard(language: str, payment_url: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=get_text(language, "subscribe_pay_link"), url=payment_url)],
        ]
    )


async def send_subscription_offers(
    *,
    bot: Bot,
    chat_id: int,
    language: str,
    api_client,
    telegram_id: int,
) -> bool:
    try:
        plans = await api_client.list_subscription_plans(telegram_id=telegram_id)
    except ApiClientError:
        logger.exception("Failed to load subscription plans telegram_id=%s", telegram_id)
        await bot.send_message(chat_id, get_text(language, "error"))
        return False

    if not plans:
        await bot.send_message(chat_id, get_text(language, "subscribe_no_plans"))
        return False

    await bot.send_message(
        chat_id,
        get_text(language, "subscribe_prompt"),
        reply_markup=build_plan_choice_keyboard(language, plans),
    )
    return True


async def create_payment_link(
    *,
    message: Message,
    language: str,
    api_client,
    telegram_id: int,
    plan_id: int,
) -> bool:
    try:
        order = await api_client.create_payment_order(telegram_id=telegram_id, plan_id=plan_id)
    except ApiClientError as exc:
        logger.exception(
            "Failed to create payment order telegram_id=%s plan_id=%s status=%s",
            telegram_id,
            plan_id,
            exc.status,
        )
        error_text = get_text(language, "subscribe_payment_failed")
        payload = exc.payload if isinstance(exc.payload, dict) else {}
        payment_error = payload.get("payment_error") or payload.get("detail")
        if payment_error:
            error_text = f"{error_text}\n{payment_error}"
        await message.answer(error_text)
        return False

    payment_url = order.get("payment_url")
    if not payment_url:
        error_text = get_text(language, "subscribe_payment_failed")
        payment_error = order.get("payment_error")
        if payment_error:
            error_text = f"{error_text}\n{payment_error}"
        await message.answer(error_text)
        return False

    await message.answer(
        get_text(language, "subscribe_payment_ready"),
        reply_markup=build_payment_url_keyboard(language, payment_url),
    )
    return True
