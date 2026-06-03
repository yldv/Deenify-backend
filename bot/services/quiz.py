from aiogram import Bot
from aiogram.enums import PollType
from aiogram.fsm.context import FSMContext

from bot.api_client import ApiClientError, BlockedUserError, NotFoundError, PaymentRequiredError
from bot.keyboards import home_keyboard
from bot.poll_sessions import remember_poll
from bot.states import TakingTest
from bot.texts import get_text
from bot.uz_cyrillic import localize_quiz_content
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


def build_poll_explanation(description: str) -> str | None:
    """Poll explanation (lamp / after answer): Manba only — uz/uz_cy/ru from API."""
    source = (description or "").strip()
    return clip_text(source, POLL_EXPLANATION_LIMIT) if source else None


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
    ) -> bool:
        if isinstance(exc, PaymentRequiredError):
            free_limit = 10
            if isinstance(exc.payload, dict):
                free_limit = exc.payload.get("progress", {}).get("free_limit", free_limit)
            await state.clear()
            await bot.send_message(
                chat_id,
                get_text(language, "quiz_subscription_required", free_limit=free_limit),
                reply_markup=home_keyboard(language),
            )
            return False
        if isinstance(exc, BlockedUserError):
            await state.clear()
            await bot.send_message(
                chat_id,
                get_text(language, "blocked"),
                reply_markup=home_keyboard(language),
            )
            return False
        if isinstance(exc, NotFoundError):
            await state.clear()
            await bot.send_message(
                chat_id,
                get_text(language, "not_found"),
                reply_markup=home_keyboard(language),
            )
            return False
        if isinstance(exc, ApiClientError):
            await state.clear()
            await bot.send_message(
                chat_id,
                get_text(language, "error"),
                reply_markup=home_keyboard(language),
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
    ) -> bool:
        question = localize_quiz_content(question, language)
        answers = question.get("answers", [])
        if not answers:
            await state.clear()
            await bot.send_message(
                chat_id,
                get_text(language, "quiz_no_questions"),
                reply_markup=home_keyboard(language),
            )
            return False

        await bot.send_message(chat_id, format_progress_header(language, progress))

        poll_message = await bot.send_poll(
            chat_id,
            question=clip_text(question["question"], POLL_QUESTION_LIMIT),
            options=[clip_text(answer["text"], POLL_OPTION_LIMIT) for answer in answers],
            type=PollType.QUIZ,
            correct_option_id=int(question.get("correct_option_index", 0)),
            is_anonymous=True,
            explanation=build_poll_explanation(question.get("description", "")),
        )

        remember_poll(
            poll_id=poll_message.poll.id,
            question=question,
            language=language,
            telegram_id=chat_id,
        )

        await state.set_state(TakingTest.answering)
        await state.update_data(
            current_question=question,
            active_poll_id=str(poll_message.poll.id),
            language=language,
            telegram_id=chat_id,
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
            return await self._send_api_error(
                bot=bot,
                chat_id=chat_id,
                state=state,
                language=language,
                exc=exc,
            )

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
                reply_markup=home_keyboard(language),
            )
            return False

        question = data.get("question")
        if not question:
            await state.clear()
            await bot.send_message(
                chat_id,
                get_text(language, "quiz_no_questions"),
                reply_markup=home_keyboard(language),
            )
            return False

        return await self.show_question(
            bot=bot,
            chat_id=chat_id,
            state=state,
            question=question,
            progress=data.get("progress", {}),
            language=language,
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
            reply_markup=home_keyboard(language),
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
        except (PaymentRequiredError, ApiClientError) as exc:
            return await self._send_api_error(
                bot=bot,
                chat_id=chat_id,
                state=state,
                language=language,
                exc=exc,
            )

        if result.get("is_round_complete"):
            await state.clear()
            await bot.send_message(
                chat_id,
                get_text(language, "quiz_round_complete"),
                reply_markup=home_keyboard(language),
            )
            return False

        return await self.load_next(
            bot=bot,
            chat_id=chat_id,
            state=state,
            telegram_id=telegram_id,
            language=language,
        )
