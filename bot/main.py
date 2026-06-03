import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.enums import UpdateType
from aiogram.fsm.storage.memory import MemoryStorage

from .api_client import BackendApiClient
from .config import load_config
from .handlers import setup_routers


async def main():
    logging.basicConfig(level=logging.INFO)
    config = load_config()

    bot = Bot(token=config.bot_token)
    dispatcher = Dispatcher(storage=MemoryStorage())
    dispatcher.include_router(setup_routers())

    api_client = BackendApiClient(base_url=config.backend_base_url)
    await dispatcher.start_polling(
        bot,
        api_client=api_client,
        bot_config=config,
        allowed_updates=[
            UpdateType.MESSAGE,
            UpdateType.CALLBACK_QUERY,
            UpdateType.POLL_ANSWER,
        ],
    )


if __name__ == "__main__":
    asyncio.run(main())
