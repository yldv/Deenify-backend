import logging

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, PollAnswer

from bot.context import get_language
from bot.keyboards import home_keyboard
from bot.poll_sessions import forget_poll, get_poll_session, remember_poll
from bot.services.quiz import QuizMessenger
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


@router.message(Command("test"))
@router.message(F.text.in_(all_button_texts("take_test")))
async def take_test_button(message: Message, state: FSMContext, api_client):
    await _run_take_test(message, state, api_client)


@router.message(Command("restart"))
@router.message(F.text.in_(all_button_texts("restart_from_start")))
async def restart_from_start_button(message: Message, state: FSMContext, api_client):
    await _run_restart_from_start(message, state, api_client)


@router.poll_answer()
async def poll_answer_handler(poll_answer: PollAnswer, state: FSMContext, api_client, bot: Bot):
    if not poll_answer.option_ids:
        return

    poll_id = str(poll_answer.poll_id)
    session = get_poll_session(poll_id)
    data = await state.get_data()

    if session:
        question = session["question"]
        language = normalize_language(session["language"])
        telegram_id = session["telegram_id"]
    else:
        if poll_id != str(data.get("active_poll_id", "")):
            logger.warning(
                "Ignored poll_answer: unknown poll_id=%s active_poll_id=%s",
                poll_id,
                data.get("active_poll_id"),
            )
            language = normalize_language(data.get("language", "uz"))
            chat_id = poll_answer.user.id if poll_answer.user else None
            if chat_id:
                await bot.send_message(
                    chat_id,
                    get_text(language, "quiz_session_expired"),
                    reply_markup=home_keyboard(language),
                )
            await state.clear()
            return

        question = data.get("current_question")
        if not question:
            logger.warning("Ignored poll_answer: no current_question in FSM poll_id=%s", poll_id)
            return
        language = normalize_language(data.get("language", "uz"))
        telegram_id = poll_answer.user.id if poll_answer.user else data.get("telegram_id")

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

    forget_poll(poll_id)
    quiz = QuizMessenger(api_client)
    await quiz.process_answer(
        bot=bot,
        chat_id=telegram_id,
        state=state,
        telegram_id=telegram_id,
        language=language,
        question=question,
        answer_id=answers[option_index]["id"],
    )
