from aiogram import Bot
from aiogram.enums import PollType
from aiogram.fsm.context import FSMContext

from bot.api_client import ApiClientError, BlockedUserError, NotFoundError, PaymentRequiredError
from bot.keyboards import home_keyboard  # used by quiz_reply_keyboard
from bot.services.payment import send_subscription_offers
from bot.poll_sessions import remember_poll
from bot.states import TakingTest
from bot.texts import get_text
from bot.uz_cyrillic import localize_quiz_content, localize_text
from core.constants import API_ROUND_COMPLETE

POLL_QUESTION_LIMIT = 300
POLL_OPTION_LIMIT = 100
POLL_EXPLANATION_LIMIT = 200


def format_progress_header(language: str, progress: dict) -> str:
    return get_text(
        language,
        "quiz_progress",
        answered=progress.get("answered_count", 0),
        total=progress.get("total_questions", 0),
    )


def clip_text(text: str, limit: int) -> str:
    value = (text or "").strip()
    if len(value) <= limit:
        return value
    return value[: limit - 1] + "…"


def build_poll_explanation(description: str, explanation: str = "") -> str | None:
    """Poll explanation (lamp): manba + tushuntirish, Telegram shows mainly on wrong answers."""
    parts = [p.strip() for p in (description, explanation) if (p or "").strip()]
    if not parts:
        return None
    return clip_text("\n".join(parts), POLL_EXPLANATION_LIMIT)


def quiz_reply_keyboard(language: str, *, is_premium: bool = False):
    """Home menu keyboard — keep visible during the quiz flow."""
    return home_keyboard(language, is_premium=is_premium)


class QuizMessenger:
    def __init__(self, api_client):
        self.api = api_client

    async def _send_api_error(
        self,
        *,
        bot: Bot,
        chat_id: int,
        state: FSMContext,
        language: str,
        exc: Exception,
        is_premium: bool = False,
    ) -> bool:
        if isinstance(exc, PaymentRequiredError):
            free_limit = 10
            if isinstance(exc.payload, dict):
                free_limit = exc.payload.get("progress", {}).get("free_limit", free_limit)
            await state.clear()
            prompt_message = await bot.send_message(
                chat_id,
                get_text(language, "quiz_subscription_required", free_limit=free_limit),
                reply_markup=quiz_reply_keyboard(language, is_premium=is_premium),
            )
            await send_subscription_offers(
                bot=bot,
                chat_id=chat_id,
                language=language,
                api_client=self.api,
                telegram_id=chat_id,
                prompt_message_id=prompt_message.message_id,
            )
            return False
        if isinstance(exc, BlockedUserError):
            await state.clear()
            await bot.send_message(
                chat_id,
                get_text(language, "blocked"),
                reply_markup=quiz_reply_keyboard(language, is_premium=is_premium),
            )
            return False
        if isinstance(exc, NotFoundError):
            await state.clear()
            await bot.send_message(
                chat_id,
                get_text(language, "not_found"),
                reply_markup=quiz_reply_keyboard(language, is_premium=is_premium),
            )
            return False
        if isinstance(exc, ApiClientError):
            await state.clear()
            await bot.send_message(
                chat_id,
                get_text(language, "error"),
                reply_markup=quiz_reply_keyboard(language, is_premium=is_premium),
            )
            return False
        raise exc

    async def show_question(
        self,
        *,
        bot: Bot,
        chat_id: int,
        state: FSMContext,
        question: dict,
        progress: dict,
        language: str,
        telegram_id: int,
    ) -> bool:
        question = localize_quiz_content(question, language)
        is_premium = bool(progress.get("is_premium"))
        keyboard = quiz_reply_keyboard(language, is_premium=is_premium)
        answers = question.get("answers", [])
        if not answers:
            await state.clear()
            await bot.send_message(
                chat_id,
                get_text(language, "quiz_no_questions"),
                reply_markup=keyboard,
            )
            return False

        await bot.send_message(
            chat_id,
            format_progress_header(language, progress),
            reply_markup=keyboard,
        )

        # is_anonymous=False is required: Telegram does not send poll_answer for anonymous polls.
        poll_message = await bot.send_poll(
            chat_id,
            question=clip_text(question["question"], POLL_QUESTION_LIMIT),
            options=[clip_text(answer["text"], POLL_OPTION_LIMIT) for answer in answers],
            type=PollType.QUIZ,
            correct_option_id=int(question.get("correct_option_index", 0)),
            is_anonymous=False,
            explanation=build_poll_explanation(
                question.get("description", ""),
                question.get("explanation", ""),
            ),
            reply_markup=keyboard,
        )

        poll_id = str(poll_message.poll.id)
        remember_poll(
            poll_id=poll_id,
            question=question,
            language=language,
            telegram_id=telegram_id,
        )

        await state.set_state(TakingTest.answering)
        await state.update_data(
            current_question=question,
            active_poll_id=poll_id,
            language=language,
            telegram_id=telegram_id,
            is_premium=is_premium,
        )
        return True

    async def load_next(
        self,
        *,
        bot: Bot,
        chat_id: int,
        state: FSMContext,
        telegram_id: int,
        language: str,
        restart_if_complete: bool = False,
    ) -> bool:
        try:
            data = await self.api.get_quiz_next(telegram_id=telegram_id, language=language)
        except (PaymentRequiredError, BlockedUserError, NotFoundError, ApiClientError) as exc:
            is_premium = False
            if isinstance(exc, PaymentRequiredError) and isinstance(exc.payload, dict):
                is_premium = bool(exc.payload.get("progress", {}).get("is_premium"))
            return await self._send_api_error(
                bot=bot,
                chat_id=chat_id,
                state=state,
                language=language,
                exc=exc,
                is_premium=is_premium,
            )

        progress = data.get("progress") or {}
        is_premium = bool(progress.get("is_premium"))

        if data.get("code") == API_ROUND_COMPLETE:
            if restart_if_complete:
                return await self.restart_from_start(
                    bot=bot,
                    chat_id=chat_id,
                    state=state,
                    telegram_id=telegram_id,
                    language=language,
                    start_question=True,
                )

            await state.clear()
            await bot.send_message(
                chat_id,
                get_text(language, "quiz_round_complete"),
                reply_markup=quiz_reply_keyboard(language, is_premium=is_premium),
            )
            return False

        question = data.get("question")
        if not question:
            await state.clear()
            await bot.send_message(
                chat_id,
                get_text(language, "quiz_no_questions"),
                reply_markup=quiz_reply_keyboard(language, is_premium=is_premium),
            )
            return False

        return await self.show_question(
            bot=bot,
            chat_id=chat_id,
            state=state,
            question=question,
            progress=progress,
            language=language,
            telegram_id=telegram_id,
        )

    async def restart_from_start(
        self,
        *,
        bot: Bot,
        chat_id: int,
        state: FSMContext,
        telegram_id: int,
        language: str,
        start_question: bool = True,
    ) -> bool:
        await state.clear()
        try:
            await self.api.reset_quiz_progress(telegram_id=telegram_id)
        except (PaymentRequiredError, BlockedUserError, NotFoundError, ApiClientError) as exc:
            return await self._send_api_error(
                bot=bot,
                chat_id=chat_id,
                state=state,
                language=language,
                exc=exc,
            )

        await bot.send_message(
            chat_id,
            get_text(language, "quiz_reset_hint"),
            reply_markup=quiz_reply_keyboard(language),
        )
        if not start_question:
            return True

        return await self.load_next(
            bot=bot,
            chat_id=chat_id,
            state=state,
            telegram_id=telegram_id,
            language=language,
            restart_if_complete=False,
        )

    async def process_answer(
        self,
        *,
        bot: Bot,
        chat_id: int,
        state: FSMContext,
        telegram_id: int,
        language: str,
        question: dict,
        answer_id: int,
    ) -> bool:
        try:
            result = await self.api.submit_quiz_answer(
                telegram_id=telegram_id,
                test_id=question["id"],
                answer_id=answer_id,
                language=language,
            )
        except (PaymentRequiredError, BlockedUserError, NotFoundError, ApiClientError) as exc:
            state_data = await state.get_data()
            is_premium = bool(state_data.get("is_premium"))
            if isinstance(exc, PaymentRequiredError) and isinstance(exc.payload, dict):
                is_premium = bool(exc.payload.get("progress", {}).get("is_premium"))
            return await self._send_api_error(
                bot=bot,
                chat_id=chat_id,
                state=state,
                language=language,
                exc=exc,
                is_premium=is_premium,
            )

        is_premium = bool(result.get("progress", {}).get("is_premium"))
        keyboard = quiz_reply_keyboard(language, is_premium=is_premium)
        outcome_key = "quiz_correct" if result.get("is_correct") else "quiz_wrong"
        await bot.send_message(chat_id, get_text(language, outcome_key), reply_markup=keyboard)

        explanation = localize_text((result.get("explanation") or "").strip(), language)
        if explanation:
            await bot.send_message(
                chat_id,
                get_text(language, "quiz_hint", text=explanation),
                reply_markup=keyboard,
            )

        if result.get("is_round_complete"):
            await state.clear()
            await bot.send_message(
                chat_id,
                get_text(language, "quiz_round_complete"),
                reply_markup=keyboard,
            )
            return False

        return await self.load_next(
            bot=bot,
            chat_id=chat_id,
            state=state,
            telegram_id=telegram_id,
            language=language,
        )
