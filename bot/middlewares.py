"""Aiogram middlewares."""

import time
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

from bot.api_client import ApiClientError
from bot.texts import normalize_language

# How often (seconds) to re-read the user's language from the backend.
# Keeps the bot in sync when the language is changed elsewhere (e.g. the
# payment page) without hitting the API on every single update.
LANGUAGE_SYNC_INTERVAL = 10


class LanguageSyncMiddleware(BaseMiddleware):
    """Refresh the FSM language from the backend so external language changes
    (payment page, admin) take effect on the user's next bot interaction."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        state = data.get("state")
        api_client = data.get("api_client")
        user = data.get("event_from_user")
        if state is not None and api_client is not None and user is not None:
            try:
                sdata = await state.get_data()
                current = sdata.get("language")
                now = time.time()
                last = sdata.get("language_synced_at", 0)
                if current and (now - last) >= LANGUAGE_SYNC_INTERVAL:
                    backend_user = await api_client.get_user(telegram_id=user.id)
                    backend_lang = normalize_language(
                        (backend_user or {}).get("language") or current
                    )
                    updates: dict[str, Any] = {"language_synced_at": now}
                    if backend_lang and backend_lang != current:
                        updates["language"] = backend_lang
                    await state.update_data(**updates)
            except ApiClientError:
                pass
            except Exception:  # noqa: BLE001 - never break the update on a sync hiccup
                pass
        return await handler(event, data)
