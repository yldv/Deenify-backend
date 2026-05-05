from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from bot.api_client import ApiClientError, NotFoundError
from bot.texts import get_text, normalize_language

router = Router()


async def get_language(state: FSMContext) -> str:
    data = await state.get_data()
    return normalize_language(data.get("language", "uz"))


@router.message(F.text.in_([
    get_text("uz", "profile"),
    get_text("ru", "profile"),
    get_text("en", "profile"),
]))
async def profile_button(message: Message, state: FSMContext, api_client):
    language = await get_language(state)
    try:
        stats = await api_client.get_statistics(telegram_id=message.from_user.id)
    except NotFoundError:
        await message.answer(get_text(language, "not_found"))
        return
    except ApiClientError:
        await message.answer(get_text(language, "error"))
        return

    premium_until = stats.get("premium_until") or "-"
    if stats.get("is_premium") and premium_until == "-":
        premium_until = get_text(language, "unlimited")

    await message.answer(
        get_text(
            language,
            "profile_text",
            premium=get_text(language, "yes") if stats.get("is_premium") else get_text(language, "no"),
            premium_until=premium_until,
            free_used=stats.get("free_tests_used", 0),
            sessions=stats.get("total_sessions", 0),
            answers=stats.get("total_answers", 0),
            correct=stats.get("correct_answers", 0),
            wrong=stats.get("wrong_answers", 0),
            score=stats.get("score_percent", 0),
        )
    )
