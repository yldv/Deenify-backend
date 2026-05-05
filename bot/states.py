from aiogram.fsm.state import State, StatesGroup


class ChoosingLanguage(StatesGroup):
    language = State()


class ChoosingTestType(StatesGroup):
    test_type = State()


class TakingTest(StatesGroup):
    answering = State()


class ChoosingPlan(StatesGroup):
    plan = State()
