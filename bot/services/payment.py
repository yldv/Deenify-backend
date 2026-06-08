import logging
from decimal import Decimal, ROUND_HALF_UP

from aiogram import Bot
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message

from bot.api_client import ApiClientError
from bot.texts import get_text

logger = logging.getLogger(__name__)

PLAN_CALLBACK_PREFIX = "pay_plan:"


def normalize_payment_url(url: str) -> str:
    if not url:
        return url
    normalized = str(url).strip()
    for host in ("checkout.atmos.uz", "dev-checkout.atmos.uz", "checkout.pays.uz"):
        normalized = normalized.replace(f"http://{host}", f"https://{host}")
    return normalized


def format_uzs(amount) -> str:
    value = int(Decimal(str(amount)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    return f"{value:,}".replace(",", " ")


def plan_billing_months(plan: dict) -> int:
    period = plan.get("period") or "month"
    duration = int(plan.get("duration") or 1)
    if period == "year":
        return 12 * duration
    if period == "month":
        return max(duration, 1)
    if period == "week":
        return max(duration, 1)
    if period == "day":
        return 1
    return 1


def plan_button_label(language: str, plan: dict) -> str:
    name = plan.get("name", "Premium")
    price = Decimal(str(plan.get("price") or 0))
    months = plan_billing_months(plan)
    period = plan.get("period") or "month"

    if period == "year" or months >= 12:
        monthly = (price / Decimal(months)).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        return get_text(
            language,
            "subscribe_plan_button_yearly",
            name=name,
            monthly_price=format_uzs(monthly),
            months=months,
        )

    return get_text(
        language,
        "subscribe_plan_button_monthly",
        name=name,
        price=format_uzs(price),
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
            [
                InlineKeyboardButton(
                    text=get_text(language, "subscribe_pay_link"),
                    url=normalize_payment_url(payment_url),
                )
            ],
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

    payment_url = normalize_payment_url(order.get("payment_url") or "")
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
