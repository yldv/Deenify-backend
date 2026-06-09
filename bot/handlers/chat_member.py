import logging

from aiogram import Router
from aiogram.types import ChatMemberUpdated

from ..api_client import BackendApiClient, NotFoundError

logger = logging.getLogger(__name__)

router = Router()

_INACTIVE_STATUSES = frozenset({"kicked", "left"})
_ACTIVE_STATUSES = frozenset({"member", "administrator"})


@router.my_chat_member()
async def on_my_chat_member(event: ChatMemberUpdated, api_client: BackendApiClient):
    if event.chat.type != "private":
        return

    telegram_id = event.from_user.id
    new_status = event.new_chat_member.status
    if new_status in _INACTIVE_STATUSES:
        bot_is_active = False
    elif new_status in _ACTIVE_STATUSES:
        bot_is_active = True
    else:
        return

    try:
        await api_client.set_bot_active(telegram_id=telegram_id, bot_is_active=bot_is_active)
    except NotFoundError:
        logger.info(
            "Ignored my_chat_member for unknown user telegram_id=%s active=%s",
            telegram_id,
            bot_is_active,
        )
    except Exception:
        logger.exception(
            "Failed to update bot_is_active telegram_id=%s active=%s",
            telegram_id,
            bot_is_active,
        )
