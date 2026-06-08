from aiogram import Router

from .help import router as help_router
from .menu import router as menu_router
from .registration import router as registration_router
from .settings import router as settings_router
from .start import router as start_router
from .tests import router as tests_router


def setup_routers() -> Router:
    router = Router()
    router.include_router(tests_router)
    router.include_router(menu_router)
    router.include_router(settings_router)
    router.include_router(start_router)
    router.include_router(registration_router)
    router.include_router(help_router)
    return router
