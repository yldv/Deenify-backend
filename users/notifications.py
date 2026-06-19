"""Direct Telegram Bot API helpers used by the backend.

After a payment is confirmed the bot process is not in the loop (the user paid on
a web page), so the backend talks to Telegram directly to:
  * delete the subscription catalog message it asked the bot to remember, and
  * send a localized "payment successful" confirmation in the chat.

Uses urllib (no extra dependency) and fails softly: a notification problem must
never break the payment flow.
"""

import json
import logging
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.conf import settings
from django.db import transaction

logger = logging.getLogger(__name__)

_TELEGRAM_API = "https://api.telegram.org"
_TIMEOUT = 10


def _telegram_request(method: str, payload: dict) -> dict | None:
    token = (getattr(settings, "BOT_TOKEN", "") or "").strip()
    if not token:
        logger.warning("BOT_TOKEN is not configured; skipping Telegram %s.", method)
        return None

    url = f"{_TELEGRAM_API}/bot{token}/{method}"
    data = json.dumps(payload).encode("utf-8")
    request = Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=_TIMEOUT) as response:
            body = response.read().decode("utf-8")
        return json.loads(body) if body else None
    except HTTPError as exc:
        detail = ""
        try:
            detail = exc.read().decode("utf-8")
        except Exception:  # noqa: BLE001
            pass
        logger.warning("Telegram %s failed (%s): %s", method, exc.code, detail)
    except (URLError, OSError, ValueError) as exc:
        logger.warning("Telegram %s request error: %s", method, exc)
    return None


def delete_telegram_message(*, chat_id, message_id) -> bool:
    if not chat_id or not message_id:
        return False
    result = _telegram_request(
        "deleteMessage", {"chat_id": chat_id, "message_id": message_id}
    )
    return bool(result and result.get("ok"))


def send_telegram_message(*, chat_id, text, parse_mode="HTML", reply_markup=None) -> bool:
    if not chat_id or not text:
        return False
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode,
        "disable_web_page_preview": True,
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup
    result = _telegram_request("sendMessage", payload)
    return bool(result and result.get("ok"))


def _home_menu_markup(language: str, *, is_premium: bool = True) -> dict:
    """Reply keyboard mirroring bot.keyboards.home_keyboard for backend-sent messages."""
    from bot.keyboards import home_keyboard_reply_dict

    return home_keyboard_reply_dict(language, is_premium=is_premium)


def _success_text(*, language: str, plan_name: str, until: str) -> str:
    from bot.texts import get_text

    return get_text(
        language,
        "payment_success_notification",
        plan_name=plan_name,
        until=until,
    )


def _localized_plan_name(plan, language: str) -> str:
    """Return the plan name in the user's language (modeltranslation field)."""
    if not plan:
        return "Premium"
    localized = getattr(plan, f"name_{language}", None)
    return (localized or plan.name or "Premium").strip()


def _format_until(*, subscription, language: str) -> str:
    from bot.texts import get_text

    if subscription is None or subscription.expires_at is None:
        return get_text(language, "payment_success_lifetime")
    return subscription.expires_at.strftime("%d.%m.%Y")


def notify_payment_success(order) -> None:
    """Delete the catalog message and confirm the payment in the user's chat.

    Idempotent: guarded by ``AtmosOrder.success_notified`` so callback + apply +
    return polling can all call it without sending duplicates.
    """
    try:
        with transaction.atomic():
            locked = (
                type(order)
                .objects.select_for_update()
                .select_related("user", "plan")
                .get(pk=order.pk)
            )
            if locked.success_notified:
                return
            locked.success_notified = True
            locked.save(update_fields=("success_notified", "updated_at"))
            order = locked
    except Exception:  # noqa: BLE001
        logger.exception("Failed to lock order for success notification pk=%s", order.pk)
        return

    user = order.user
    if not user or not user.telegram_id:
        return

    language = user.get_content_language()
    chat_id = user.telegram_id

    if user.offer_chat_id and (user.offer_message_id or user.offer_prompt_message_id):
        for message_id in (user.offer_message_id, user.offer_prompt_message_id):
            if message_id:
                delete_telegram_message(
                    chat_id=user.offer_chat_id, message_id=message_id
                )
        user.offer_message_id = None
        user.offer_prompt_message_id = None
        user.offer_chat_id = None
        try:
            user.save(
                update_fields=(
                    "offer_message_id",
                    "offer_prompt_message_id",
                    "offer_chat_id",
                    "updated_at",
                )
            )
        except Exception:  # noqa: BLE001
            logger.exception("Failed to clear offer message for user=%s", chat_id)

    subscription = getattr(order, "premium_subscription", None)
    plan_name = _localized_plan_name(order.plan, language)
    until = _format_until(subscription=subscription, language=language)
    send_telegram_message(
        chat_id=chat_id,
        text=_success_text(language=language, plan_name=plan_name, until=until),
        reply_markup=_home_menu_markup(language, is_premium=True),
    )


def notify_referral_reward(*, referrer, invited_user, days) -> None:
    """Tell the inviter they earned bonus premium days for an invited user's payment."""
    if not referrer or not referrer.telegram_id:
        return
    from bot.texts import get_text

    language = referrer.get_content_language()
    invited_name = (invited_user.full_name or invited_user.username or "").strip() or "do'stingiz"
    text = get_text(
        language,
        "referral_reward_notification",
        days=days,
        invited_name=invited_name,
    )
    send_telegram_message(chat_id=referrer.telegram_id, text=text)
