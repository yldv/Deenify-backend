from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.api_client import ApiClientError, BlockedUserError, NotFoundError, PaymentRequiredError
from bot.keyboards import answers_keyboard, back_menu_keyboard, plans_keyboard, test_type_keyboard
from bot.states import ChoosingTestType, TakingTest
from bot.texts import get_text, normalize_language

router = Router()


async def get_language(state: FSMContext) -> str:
    data = await state.get_data()
    return normalize_language(data.get("language", "uz"))


async def show_premium_plans(message: Message, language: str, api_client):
    try:
        plans = await api_client.get_subscription_plans(language=language)
    except ApiClientError:
        await message.answer(get_text(language, "error"))
        return

    if plans:
        await message.answer(
            get_text(language, "free_limit_finished"),
            reply_markup=plans_keyboard(plans),
        )
    else:
        await message.answer(get_text(language, "free_limit_finished"))


async def send_question(message: Message, state: FSMContext):
    data = await state.get_data()
    language = normalize_language(data.get("language", "uz"))
    questions = data.get("questions", [])
    index = data.get("current_question_index", 0)

    if index >= len(questions):
        await finish_current_session(message, state, data)
        return

    question = questions[index]
    await message.answer(
        f"{index + 1}/{len(questions)}\n\n{question['question']}",
        reply_markup=answers_keyboard(question.get("answers", [])),
    )
    await state.set_state(TakingTest.answering)
    await state.update_data(current_question=question)


async def finish_current_session(message: Message, state: FSMContext, data=None, api_client=None):
    data = data or await state.get_data()
    language = normalize_language(data.get("language", "uz"))
    client = api_client or data.get("api_client")
    if client is None:
        await message.answer(get_text(language, "error"), reply_markup=back_menu_keyboard(language))
        return

    result = await client.finish_session(
        session_id=data["session_id"],
        telegram_id=message.chat.id,
    )
    await message.answer(
        get_text(
            language,
            "final_result",
            correct=result.get("correct_answers", 0),
            wrong=result.get("wrong_answers", 0),
            total=result.get("total_questions", 0),
            score=result.get("score_percent", 0),
        ),
        reply_markup=back_menu_keyboard(language),
    )
    await state.update_data(session_id=None, questions=[], current_question_index=0)


@router.message(F.text.in_([
    get_text("uz", "take_test"),
    get_text("ru", "take_test"),
    get_text("en", "take_test"),
]))
async def take_test_button(message: Message, state: FSMContext, api_client):
    language = await get_language(state)
    try:
        stats = await api_client.get_statistics(telegram_id=message.from_user.id)
    except BlockedUserError:
        await message.answer(get_text(language, "blocked"))
        return
    except NotFoundError:
        await message.answer(get_text(language, "not_found"))
        return
    except ApiClientError:
        await message.answer(get_text(language, "error"))
        return

    if stats.get("free_tests_used", 0) >= 10 and not stats.get("is_premium"):
        await show_premium_plans(message, language, api_client)
        return

    await state.set_state(ChoosingTestType.test_type)
    await message.answer(get_text(language, "choose_test_type"), reply_markup=test_type_keyboard(language))


@router.callback_query(F.data.startswith("test_type:"))
async def test_type_selected(callback: CallbackQuery, state: FSMContext, api_client):
    language = await get_language(state)
    test_type = callback.data.split(":", 1)[1]
    try:
        session = await api_client.start_test_session(
            telegram_id=callback.from_user.id,
            test_type=test_type,
            language=language,
        )
    except PaymentRequiredError:
        await show_premium_plans(callback.message, language, api_client)
        await callback.answer()
        return
    except BlockedUserError:
        await callback.message.answer(get_text(language, "blocked"))
        await callback.answer()
        return
    except ApiClientError:
        await callback.message.answer(get_text(language, "error"))
        await callback.answer()
        return

    questions = session.get("questions", [])
    if not questions:
        await callback.message.answer(get_text(language, "no_questions"))
        await callback.answer()
        return

    await state.update_data(
        session_id=session["session_id"],
        test_type=test_type,
        questions=questions,
        current_question_index=0,
    )
    await send_question(callback.message, state)
    await callback.answer()


@router.callback_query(F.data.startswith("answer:"))
async def answer_selected(callback: CallbackQuery, state: FSMContext, api_client):
    data = await state.get_data()
    language = normalize_language(data.get("language", "uz"))
    question = data.get("current_question")
    if not question or not data.get("session_id"):
        await callback.answer()
        return

    answer_id = int(callback.data.split(":", 1)[1])
    try:
        result = await api_client.submit_answer(
            session_id=data["session_id"],
            telegram_id=callback.from_user.id,
            test_id=question["id"],
            answer_id=answer_id,
            language=language,
        )
    except PaymentRequiredError:
        await show_premium_plans(callback.message, language, api_client)
        await callback.answer()
        return
    except ApiClientError as exc:
        await callback.message.answer(str(exc) or get_text(language, "error"))
        await callback.answer()
        return

    explanation = result.get("explanation") or ""
    verdict = get_text(language, "correct") if result.get("is_correct") else get_text(language, "wrong")
    await callback.message.answer(f"{verdict}\n\n{explanation}".strip())

    next_index = data.get("current_question_index", 0) + 1
    await state.update_data(current_question_index=next_index)
    if next_index >= len(data.get("questions", [])):
        await finish_current_session(callback.message, state, api_client=api_client)
    else:
        await send_question(callback.message, state)
    await callback.answer()
