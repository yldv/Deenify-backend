from aiogram import Router

from bot.middlewares import LanguageSyncMiddleware, RegistrationGuardMiddleware

from .chat_member import router as chat_member_router
from .feedback import router as feedback_router
from .help import router as help_router
from .menu import router as menu_router
from .registration import router as registration_router
from .settings import router as settings_router
from .start import router as start_router
from .subscription import router as subscription_router
from .tests import router as tests_router


def setup_routers() -> Router:
    router = Router()
    language_sync = LanguageSyncMiddleware()
    registration_guard = RegistrationGuardMiddleware()
    router.message.middleware(language_sync)
    router.message.middleware(registration_guard)
    router.callback_query.middleware(language_sync)
    router.callback_query.middleware(registration_guard)
    router.poll_answer.middleware(registration_guard)
    router.include_router(feedback_router)
    router.include_router(subscription_router)
    router.include_router(start_router)
    router.include_router(registration_router)
    router.include_router(tests_router)
    router.include_router(menu_router)
    router.include_router(settings_router)
    router.include_router(help_router)
    router.include_router(chat_member_router)
    return router
