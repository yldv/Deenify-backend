from aiogram.fsm.state import State, StatesGroup


class ChoosingLanguage(StatesGroup):
    language = State()


class RegistrationState(StatesGroup):
    waiting_for_phone = State()


class SettingsState(StatesGroup):
    menu = State()


class HelpState(StatesGroup):
    menu = State()
    waiting_for_message = State()


class TakingTest(StatesGroup):
    answering = State()
