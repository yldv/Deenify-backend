from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, PollAnswer

from bot.context import get_language
from bot.services.quiz import QuizMessenger
from bot.texts import all_button_texts, normalize_language

router = Router()


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

    data = await state.get_data()
    if poll_answer.poll_id != data.get("active_poll_id"):
        return

    question = data.get("current_question")
    if not question:
        return

    language = normalize_language(data.get("language", "uz"))
    option_index = poll_answer.option_ids[0]
    answers = question.get("answers", [])
    if option_index >= len(answers):
        return

    quiz = QuizMessenger(api_client)
    await quiz.process_answer(
        bot=bot,
        chat_id=poll_answer.user.id,
        state=state,
        telegram_id=poll_answer.user.id,
        language=language,
        question=question,
        answer_id=answers[option_index]["id"],
    )
