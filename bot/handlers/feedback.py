import logging

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.api_client import ApiClientError
from bot.config import BotConfig
from bot.context import get_language, preserve_language
from bot.handlers.common import resolve_is_premium, show_home_menu
from bot.keyboards import (
    FEEDBACK_DECLINE_PREFIX,
    FEEDBACK_REASON_PREFIX,
    FEEDBACK_SKIP_PREFIX,
    feedback_reasons_keyboard,
)
from bot.states import FeedbackState
from bot.texts import get_text

router = Router()
logger = logging.getLogger(__name__)

_VALID_CONTEXTS = {"declined", "canceled"}


async def start_feedback_survey(
    *, message: Message, state: FSMContext, language: str, context: str = "declined"
):
    """Show the feedback reasons keyboard (used after a cancel)."""
    await message.answer(
        get_text(language, "feedback_intro"),
        reply_markup=feedback_reasons_keyboard(language, context),
    )


async def _forward_to_admins(
    *,
    bot: Bot,
    bot_config: BotConfig,
    user,
    context: str,
    reason: str,
    text: str,
):
    if not bot_config.admin_ids:
        logger.warning("ADMIN_IDS empty; feedback from %s not forwarded", user.id)
        return
    reason_label = get_text("uz", f"feedback_reason_{reason}") if reason else "—"
    admin_text = (
        f"📝 Feedback ({context})\n"
        f"From: {user.full_name} (@{user.username or '—'})\n"
        f"ID: {user.id}\n"
        f"Reason: {reason_label}\n\n"
        f"{text or '—'}"
    )
    for admin_id in bot_config.admin_ids:
        try:
            await bot.send_message(admin_id, admin_text)
        except Exception:  # noqa: BLE001
            logger.exception("Failed to send feedback to admin_id=%s", admin_id)


async def _save_feedback(*, api_client, telegram_id, context, reason="", text=""):
    try:
        await api_client.send_feedback(
            telegram_id=telegram_id, context=context, reason=reason, text=text
        )
    except ApiClientError:
        logger.exception("Failed to store feedback telegram_id=%s", telegram_id)


@router.callback_query(F.data.startswith(FEEDBACK_DECLINE_PREFIX))
async def feedback_decline(callback: CallbackQuery, state: FSMContext):
    context = callback.data.removeprefix(FEEDBACK_DECLINE_PREFIX).strip()
    if context not in _VALID_CONTEXTS:
        context = "declined"
    language = await get_language(state)
    await callback.answer()
    try:
        await callback.message.edit_text(
            get_text(language, "feedback_intro"),
            reply_markup=feedback_reasons_keyboard(language, context),
        )
    except Exception:  # noqa: BLE001
        await callback.message.answer(
            get_text(language, "feedback_intro"),
            reply_markup=feedback_reasons_keyboard(language, context),
        )


@router.callback_query(F.data.startswith(FEEDBACK_REASON_PREFIX))
async def feedback_reason(
    callback: CallbackQuery,
    state: FSMContext,
    api_client,
    bot: Bot,
    bot_config: BotConfig,
):
    payload = callback.data.removeprefix(FEEDBACK_REASON_PREFIX)
    context, _, reason = payload.partition(":")
    if context not in _VALID_CONTEXTS:
        context = "declined"
    language = await get_language(state)
    await callback.answer()

    if reason == "other":
        await state.update_data(feedback_context=context)
        await state.set_state(FeedbackState.waiting_for_text)
        try:
            await callback.message.edit_text(get_text(language, "feedback_other_prompt"))
        except Exception:  # noqa: BLE001
            await callback.message.answer(get_text(language, "feedback_other_prompt"))
        return

    await _save_feedback(
        api_client=api_client,
        telegram_id=callback.from_user.id,
        context=context,
        reason=reason,
    )
    await _forward_to_admins(
        bot=bot,
        bot_config=bot_config,
        user=callback.from_user,
        context=context,
        reason=reason,
        text="",
    )
    try:
        await callback.message.edit_text(get_text(language, "feedback_thanks"))
    except Exception:  # noqa: BLE001
        await callback.message.answer(get_text(language, "feedback_thanks"))


@router.callback_query(F.data.startswith(FEEDBACK_SKIP_PREFIX))
async def feedback_skip(callback: CallbackQuery, state: FSMContext):
    language = await get_language(state)
    await callback.answer()
    try:
        await callback.message.edit_text(get_text(language, "feedback_thanks"))
    except Exception:  # noqa: BLE001
        await callback.message.answer(get_text(language, "feedback_thanks"))


@router.message(FeedbackState.waiting_for_text)
async def feedback_text(
    message: Message,
    state: FSMContext,
    api_client,
    bot: Bot,
    bot_config: BotConfig,
):
    language = await get_language(state)
    data = await state.get_data()
    context = data.get("feedback_context", "declined")
    text = (message.text or "").strip()
    if not text:
        await message.answer(get_text(language, "feedback_other_prompt"))
        return

    await _save_feedback(
        api_client=api_client,
        telegram_id=message.from_user.id,
        context=context,
        reason="other",
        text=text,
    )
    await _forward_to_admins(
        bot=bot,
        bot_config=bot_config,
        user=message.from_user,
        context=context,
        reason="other",
        text=text,
    )
    await preserve_language(state)
    await message.answer(get_text(language, "feedback_thanks"))
    is_premium = await resolve_is_premium(api_client, message.from_user.id)
    await show_home_menu(message, language, is_premium=is_premium)
