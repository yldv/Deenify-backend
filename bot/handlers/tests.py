import logging

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, PollAnswer

from bot.context import get_language
from bot.keyboards import home_keyboard
from bot.poll_sessions import forget_poll, get_poll_session
from bot.services.quiz import QuizMessenger
from bot.states import TakingTest
from bot.texts import all_button_texts, get_text, normalize_language

router = Router()
logger = logging.getLogger(__name__)


async def _run_take_test(message: Message, state: FSMContext, api_client):
    language = await get_language(state)
    await state.update_data(language=language)
    quiz = QuizMessenger(api_client)
    await quiz.load_next(
        bot=message.bot,
        chat_id=message.chat.id,
        state=state,
        telegram_id=message.from_user.id,
        language=language,
        restart_if_complete=True,
    )


async def _run_restart_from_start(message: Message, state: FSMContext, api_client):
    language = await get_language(state)
    await state.update_data(language=language)
    quiz = QuizMessenger(api_client)
    await quiz.restart_from_start(
        bot=message.bot,
        chat_id=message.chat.id,
        state=state,
        telegram_id=message.from_user.id,
        language=language,
    )


async def _resolve_quiz_context(*, session_key: str, state: FSMContext, poll_answer: PollAnswer | None = None):
    session = get_poll_session(session_key)
    data = await state.get_data()

    if session:
        return (
            session["question"],
            normalize_language(session["language"]),
            session["telegram_id"],
            None,
        )

    active_id = str(data.get("active_quiz_message_id") or data.get("active_poll_id") or "")
    if session_key != active_id:
        language = normalize_language(data.get("language", "uz"))
        return None, language, None, "expired"

    question = data.get("current_question")
    if not question:
        return None, normalize_language(data.get("language", "uz")), None, "missing_question"

    language = normalize_language(data.get("language", "uz"))
    telegram_id = data.get("telegram_id")
    if poll_answer and poll_answer.user:
        telegram_id = poll_answer.user.id
    return question, language, telegram_id, None


async def _submit_quiz_selection(
    *,
    bot: Bot,
    state: FSMContext,
    api_client,
    session_key: str,
    answer_id: int,
    chat_id: int,
    telegram_id: int,
    question: dict,
    language: str,
) -> bool:
    answers = question.get("answers", [])
    if not any(answer.get("id") == answer_id for answer in answers):
        logger.warning(
            "Ignored quiz answer: answer_id=%s not in question_id=%s session=%s",
            answer_id,
            question.get("id"),
            session_key,
        )
        return False

    forget_poll(session_key)
    quiz = QuizMessenger(api_client)
    logger.info(
        "submitting answer test_id=%s answer_id=%s telegram_id=%s",
        question.get("id"),
        answer_id,
        telegram_id,
    )
    return await quiz.process_answer(
        bot=bot,
        chat_id=chat_id,
        state=state,
        telegram_id=telegram_id,
        language=language,
        question=question,
        answer_id=answer_id,
    )


@router.message(Command("test"))
@router.message(F.text.in_(all_button_texts("take_test")))
async def take_test_button(message: Message, state: FSMContext, api_client):
    await _run_take_test(message, state, api_client)


@router.message(Command("restart"))
@router.message(F.text.in_(all_button_texts("restart_from_start")))
async def restart_from_start_button(message: Message, state: FSMContext, api_client):
    await _run_restart_from_start(message, state, api_client)


@router.callback_query(F.data.startswith("quiz:"), TakingTest.answering)
async def quiz_answer_callback(callback: CallbackQuery, state: FSMContext, api_client, bot: Bot):
    if not callback.data or not callback.message or not callback.from_user:
        await callback.answer()
        return

    parts = callback.data.split(":")
    if len(parts) != 3:
        await callback.answer()
        return

    try:
        test_id = int(parts[1])
        answer_id = int(parts[2])
    except ValueError:
        await callback.answer()
        return

    session_key = str(callback.message.message_id)
    question, language, telegram_id, error = await _resolve_quiz_context(
        session_key=session_key,
        state=state,
    )

    if error == "expired" or not question:
        await callback.answer(get_text(language, "quiz_session_expired"), show_alert=True)
        if callback.message:
            await bot.send_message(
                callback.from_user.id,
                get_text(language, "quiz_session_expired"),
                reply_markup=home_keyboard(language),
            )
        await state.clear()
        return

    if question.get("id") != test_id:
        await callback.answer(get_text(language, "error"), show_alert=True)
        return

    if not telegram_id:
        telegram_id = callback.from_user.id

    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        logger.debug("Could not remove quiz inline keyboard message_id=%s", session_key)

    selected = next((item for item in question.get("answers", []) if item.get("id") == answer_id), None)
    correct_index = question.get("correct_option_index")
    answers = question.get("answers", [])
    if (
        selected
        and isinstance(correct_index, int)
        and 0 <= correct_index < len(answers)
    ):
        feedback_key = (
            "quiz_correct"
            if selected["id"] == answers[correct_index]["id"]
            else "quiz_wrong"
        )
        await callback.answer(get_text(language, feedback_key))
    else:
        await callback.answer()

    try:
        await _submit_quiz_selection(
            bot=bot,
            state=state,
            api_client=api_client,
            session_key=session_key,
            answer_id=answer_id,
            chat_id=callback.from_user.id,
            telegram_id=telegram_id,
            question=question,
            language=language,
        )
    except Exception:
        logger.exception(
            "quiz callback failed message_id=%s user=%s",
            session_key,
            callback.from_user.id,
        )
        await bot.send_message(
            callback.from_user.id,
            get_text(language, "error"),
            reply_markup=home_keyboard(language),
        )
        await state.clear()


@router.poll_answer()
async def poll_answer_handler(poll_answer: PollAnswer, state: FSMContext, api_client, bot: Bot):
    """Legacy handler for old native quiz polls still open in chat."""
    logger.info(
        "poll_answer received poll_id=%s user=%s option_ids=%s",
        poll_answer.poll_id,
        poll_answer.user.id if poll_answer.user else None,
        poll_answer.option_ids,
    )
    if not poll_answer.option_ids:
        return

    poll_id = str(poll_answer.poll_id)
    question, language, telegram_id, error = await _resolve_quiz_context(
        session_key=poll_id,
        state=state,
        poll_answer=poll_answer,
    )

    if error == "expired" or not question:
        language = language or "uz"
        chat_id = poll_answer.user.id if poll_answer.user else None
        if chat_id:
            await bot.send_message(
                chat_id,
                get_text(language, "quiz_session_expired"),
                reply_markup=home_keyboard(language),
            )
        await state.clear()
        return

    if not telegram_id and poll_answer.user:
        telegram_id = poll_answer.user.id
    if not telegram_id:
        logger.warning("Ignored poll_answer: no telegram user poll_id=%s", poll_id)
        return

    option_index = poll_answer.option_ids[0]
    answers = question.get("answers", [])
    if option_index >= len(answers):
        logger.warning(
            "Ignored poll_answer: option_index=%s answers=%s poll_id=%s",
            option_index,
            len(answers),
            poll_id,
        )
        return

    try:
        await _submit_quiz_selection(
            bot=bot,
            state=state,
            api_client=api_client,
            session_key=poll_id,
            answer_id=answers[option_index]["id"],
            chat_id=telegram_id,
            telegram_id=telegram_id,
            question=question,
            language=language,
        )
    except Exception:
        logger.exception(
            "poll_answer failed poll_id=%s user=%s",
            poll_answer.poll_id,
            poll_answer.user.id if poll_answer.user else None,
        )
        chat_id = poll_answer.user.id if poll_answer.user else None
        if chat_id:
            await bot.send_message(
                chat_id,
                get_text(language, "error"),
                reply_markup=home_keyboard(language),
            )
        await state.clear()
