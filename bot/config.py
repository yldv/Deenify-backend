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


def load_config() -> BotConfig:
    bot_token = os.environ.get("BOT_TOKEN", "").strip()
    backend_base_url = os.environ.get("BACKEND_BASE_URL", "").strip().rstrip("/")

    if not bot_token:
        raise RuntimeError("BOT_TOKEN is required.")
    if not backend_base_url:
        raise RuntimeError("BACKEND_BASE_URL is required.")

    return BotConfig(
        bot_token=bot_token,
        backend_base_url=backend_base_url,
    )
