import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from .api_client import BackendApiClient
from .config import load_config
from .handlers import setup_routers

logger = logging.getLogger(__name__)


async def main():
    logging.basicConfig(level=logging.INFO)
    config = load_config()

    bot = Bot(token=config.bot_token)
    webhook = await bot.get_webhook_info()
    if webhook.url:
        logger.warning("Webhook was set (%s), removing for polling", webhook.url)
    await bot.delete_webhook(drop_pending_updates=False)

    dispatcher = Dispatcher(storage=MemoryStorage())
    dispatcher.include_router(setup_routers())

    api_client = BackendApiClient(base_url=config.backend_base_url)
    allowed_updates = dispatcher.resolve_used_update_types()
    if "poll_answer" not in allowed_updates:
        allowed_updates = sorted({*allowed_updates, "poll_answer"})
    logger.info("Bot polling update types: %s", allowed_updates)
    await dispatcher.start_polling(
        bot,
        api_client=api_client,
        bot_config=config,
        allowed_updates=allowed_updates,
    )


if __name__ == "__main__":
    asyncio.run(main())
