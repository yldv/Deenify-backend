from aiogram.fsm.context import FSMContext

from bot.texts import normalize_language


async def get_language(state: FSMContext) -> str:
    data = await state.get_data()
    return normalize_language(data.get("language", "uz"))


async def preserve_language(state: FSMContext, language: str | None = None) -> str:
    if language is None:
        language = await get_language(state)
    else:
        language = normalize_language(language)
    await state.clear()
    await state.update_data(language=language)
    return language
