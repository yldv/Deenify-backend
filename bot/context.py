from aiogram.fsm.context import FSMContext

from bot.texts import normalize_language


async def get_language(state: FSMContext) -> str:
    data = await state.get_data()
    return normalize_language(data.get("language", "uz"))


async def preserve_language(state: FSMContext) -> str:
    language = await get_language(state)
    await state.clear()
    await state.update_data(language=language)
    return language
