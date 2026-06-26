"""Aiogram middlewares."""

import time
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, PollAnswer, TelegramObject

from bot.api_client import ApiClientError, NotFoundError
from bot.handlers.common import prompt_phone_registration
from bot.keyboards import language_keyboard, phone_keyboard
from bot.states import ChoosingLanguage, RegistrationState
from bot.texts import get_text, normalize_language

# How often (seconds) to re-read the user's language from the backend.
# Keeps the bot in sync when the language is changed elsewhere (e.g. the
# payment page) without hitting the API on every single update.
LANGUAGE_SYNC_INTERVAL = 10

PHONE_PROMPT_COOLDOWN_SECONDS = 3


def _state_group(current: str | None, group_name: str) -> bool:
    return bool(current and current.startswith(f"{group_name}:"))


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


class RegistrationGuardMiddleware(BaseMiddleware):
    """Block bot features until the user shares a phone number.

    Users created during an interrupted registration (language chosen, phone skipped)
    are prompted again on their next message, poll answer, or button press.
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user = data.get("event_from_user")
        state = data.get("state")
        api_client = data.get("api_client")
        if user is None or state is None or api_client is None:
            return await handler(event, data)

        current_state = await state.get_state()
        if _state_group(current_state, ChoosingLanguage.__name__):
            return await handler(event, data)
        if _state_group(current_state, RegistrationState.__name__):
            return await handler(event, data)

        if isinstance(event, Message) and event.text and event.text.startswith("/start"):
            return await handler(event, data)

        try:
            backend_user = await api_client.get_user(telegram_id=user.id)
        except NotFoundError:
            if isinstance(event, Message):
                await state.set_state(ChoosingLanguage.language)
                await event.answer(
                    get_text("uz", "choose_language"),
                    reply_markup=language_keyboard(),
                )
            return
        except ApiClientError:
            return await handler(event, data)

        if backend_user.get("is_registered"):
            return await handler(event, data)

        language = normalize_language(
            backend_user.get("language") or (await state.get_data()).get("language", "uz")
        )
        await state.set_state(RegistrationState.waiting_for_phone)
        await state.update_data(language=language)

        sdata = await state.get_data()
        now = time.time()
        last_prompt = float(sdata.get("phone_prompt_at") or 0)
        if now - last_prompt < PHONE_PROMPT_COOLDOWN_SECONDS:
            return

        await state.update_data(phone_prompt_at=now)
        bot = data.get("bot")

        if isinstance(event, Message):
            await prompt_phone_registration(event, state, language=language)
            return

        if isinstance(event, PollAnswer) and bot:
            await bot.send_message(
                user.id,
                get_text(language, "phone_prompt"),
                reply_markup=phone_keyboard(language),
            )
            return

        if isinstance(event, CallbackQuery) and bot:
            await event.answer()
            target = event.message.chat.id if event.message else user.id
            await bot.send_message(
                target,
                get_text(language, "phone_prompt"),
                reply_markup=phone_keyboard(language),
            )
            return

        return
