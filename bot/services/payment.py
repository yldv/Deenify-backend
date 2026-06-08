import logging
import os
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
    if "dev-checkout.atmos.uz" in normalized:
        backend = os.environ.get("BACKEND_BASE_URL", "").strip().rstrip("/")
        if backend and "/api/" in backend:
            proxy_base = backend.split("/api/", 1)[0]
            normalized = normalized.replace("https://dev-checkout.atmos.uz", proxy_base)
            normalized = normalized.replace("http://dev-checkout.atmos.uz", proxy_base)
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


def is_yearly_plan(plan: dict) -> bool:
    return (plan.get("period") or "month") == "year" or plan_billing_months(plan) >= 12


def find_monthly_baseline(plans: list[dict]) -> dict | None:
    monthly = [
        plan
        for plan in plans
        if (plan.get("period") or "month") == "month" and int(plan.get("duration") or 1) == 1
    ]
    if not monthly:
        return None
    return min(monthly, key=lambda plan: Decimal(str(plan.get("price") or 0)))


def yearly_discount_percent(plans: list[dict], yearly_plan: dict) -> int | None:
    monthly = find_monthly_baseline(plans)
    if not monthly:
        return None
    months = plan_billing_months(yearly_plan)
    if months <= 1:
        return None
    yearly_monthly = (Decimal(str(yearly_plan.get("price") or 0)) / Decimal(months)).quantize(
        Decimal("1"), rounding=ROUND_HALF_UP
    )
    monthly_price = Decimal(str(monthly.get("price") or 0))
    if monthly_price <= 0 or yearly_monthly >= monthly_price:
        return None
    return int((Decimal("1") - yearly_monthly / monthly_price) * 100)


def sort_plans_for_display(plans: list[dict]) -> list[dict]:
    def sort_key(plan: dict):
        yearly = is_yearly_plan(plan)
        price = Decimal(str(plan.get("price") or 0))
        return (0 if yearly else 1, price)

    return sorted(plans, key=sort_key)


def plan_button_label(language: str, plan: dict, plans: list[dict]) -> str:
    name = plan.get("name", "Premium")
    price = Decimal(str(plan.get("price") or 0))
    months = plan_billing_months(plan)

    if is_yearly_plan(plan):
        monthly = (price / Decimal(months)).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        discount = yearly_discount_percent(plans, plan)
        if discount:
            return get_text(
                language,
                "subscribe_plan_button_yearly_discount",
                monthly_price=format_uzs(monthly),
                discount=discount,
            )
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


def format_plan_catalog_line(language: str, plan: dict, plans: list[dict]) -> str:
    price = Decimal(str(plan.get("price") or 0))
    months = plan_billing_months(plan)

    if is_yearly_plan(plan):
        monthly = (price / Decimal(months)).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        discount = yearly_discount_percent(plans, plan)
        if discount:
            return get_text(
                language,
                "subscribe_catalog_yearly_discount",
                monthly_price=format_uzs(monthly),
                months=months,
                total_price=format_uzs(price),
                discount=discount,
            )
        return get_text(
            language,
            "subscribe_catalog_yearly",
            monthly_price=format_uzs(monthly),
            months=months,
            total_price=format_uzs(price),
        )

    return get_text(
        language,
        "subscribe_catalog_monthly",
        price=format_uzs(price),
    )


def build_subscription_catalog_text(language: str, plans: list[dict]) -> str:
    lines = [get_text(language, "subscribe_catalog_header"), ""]
    for plan in sort_plans_for_display(plans):
        lines.append(format_plan_catalog_line(language, plan, plans))
        lines.append("")
    lines.append(get_text(language, "subscribe_catalog_footer"))
    return "\n".join(lines).strip()


def build_plan_choice_keyboard(language: str, plans: list[dict]) -> InlineKeyboardMarkup:
    rows = []
    for plan in sort_plans_for_display(plans):
        payment_url = normalize_payment_url(plan.get("payment_start_url") or "")
        if payment_url:
            rows.append(
                [
                    InlineKeyboardButton(
                        text=plan_button_label(language, plan, plans),
                        url=payment_url,
                    )
                ]
            )
        else:
            rows.append(
                [
                    InlineKeyboardButton(
                        text=plan_button_label(language, plan, plans),
                        callback_data=f"{PLAN_CALLBACK_PREFIX}{plan['id']}",
                    )
                ]
            )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def build_payment_url_keyboard(language: str, payment_url: str, total_price: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=get_text(language, "subscribe_pay_link", price=total_price),
                    url=normalize_payment_url(payment_url),
                )
            ],
        ]
    )


def find_plan(plans: list[dict], plan_id: int) -> dict | None:
    for plan in plans:
        if int(plan.get("id") or 0) == plan_id:
            return plan
    return None


def build_payment_ready_text(language: str, plan: dict, plans: list[dict]) -> str:
    price = Decimal(str(plan.get("price") or 0))
    months = plan_billing_months(plan)
    total_price = format_uzs(price)

    if is_yearly_plan(plan):
        monthly = (price / Decimal(months)).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        discount = yearly_discount_percent(plans, plan)
        yearly_key = (
            "subscribe_payment_ready_yearly_discount"
            if discount
            else "subscribe_payment_ready_yearly"
        )
        text = get_text(
            language,
            yearly_key,
            plan_name=plan.get("name", "Premium"),
            total_price=total_price,
            months=months,
            monthly_price=format_uzs(monthly),
            discount=discount or 0,
        )
    else:
        text = get_text(
            language,
            "subscribe_payment_ready_monthly",
            plan_name=plan.get("name", "Premium"),
            total_price=total_price,
        )

    return text


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
        build_subscription_catalog_text(language, plans),
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
        plans = await api_client.list_subscription_plans(telegram_id=telegram_id)
    except ApiClientError:
        logger.exception("Failed to load plans for payment telegram_id=%s", telegram_id)
        await message.answer(get_text(language, "error"))
        return False

    plan = find_plan(plans, plan_id)
    if not plan:
        await message.answer(get_text(language, "subscribe_no_plans"))
        return False

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

    total_price = format_uzs(plan.get("price") or order.get("amount") or 0)
    await message.answer(
        build_payment_ready_text(language, plan, plans),
        reply_markup=build_payment_url_keyboard(language, payment_url, total_price),
    )
    return True
