from aiogram import Router

from .payment import router as payment_router
from .profile import router as profile_router
from .start import router as start_router
from .tests import router as tests_router


def setup_routers() -> Router:
    router = Router()
    router.include_router(start_router)
    router.include_router(tests_router)
    router.include_router(payment_router)
    router.include_router(profile_router)
    return router
