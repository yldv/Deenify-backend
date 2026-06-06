import os
from dataclasses import dataclass

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None


if load_dotenv:
    load_dotenv()


@dataclass(frozen=True)
class BotConfig:
    bot_token: str
    backend_base_url: str
    bot_api_secret: str
    support_phone: str
    admin_ids: tuple[int, ...]


def load_config() -> BotConfig:
    bot_token = os.environ.get("BOT_TOKEN", "").strip()
    backend_base_url = os.environ.get("BACKEND_BASE_URL", "").strip().rstrip("/")
    bot_api_secret = os.environ.get("BOT_API_SECRET", "").strip()
    support_phone = os.environ.get("SUPPORT_PHONE", "").strip()
    admin_ids = tuple(
        int(item.strip())
        for item in os.environ.get("ADMIN_IDS", "").split(",")
        if item.strip().isdigit()
    )

    if not bot_token:
        raise RuntimeError("BOT_TOKEN is required.")
    if not backend_base_url:
        raise RuntimeError("BACKEND_BASE_URL is required.")
    if not bot_api_secret:
        raise RuntimeError("BOT_API_SECRET is required.")

    return BotConfig(
        bot_token=bot_token,
        backend_base_url=backend_base_url,
        bot_api_secret=bot_api_secret,
        support_phone=support_phone,
        admin_ids=admin_ids,
    )
