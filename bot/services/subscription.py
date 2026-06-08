from datetime import datetime

from bot.texts import get_text


def _format_dt(value, language: str) -> str:
    if not value:
        return "—"
    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return value.strftime("%d.%m.%Y %H:%M")


def build_subscription_summary(*, language: str, user: dict, free_limit: int = 10) -> str:
    subscription = user.get("subscription") or {}
    status = subscription.get("status")
    used = int(subscription.get("free_used", user.get("free_tests_used") or 0))
    limit = int(subscription.get("free_limit", free_limit))

    if status == "blocked":
        return get_text(language, "settings_subscription_blocked")

    if status == "active":
        until_raw = subscription.get("expires_at") or user.get("premium_until")
        until = "∞" if not until_raw else _format_dt(until_raw, language)
        starts_raw = subscription.get("starts_at") or user.get("premium_starts_at")
        return get_text(
            language,
            "settings_subscription_active",
            plan=subscription.get("plan") or user.get("premium_plan") or "Premium",
            starts=_format_dt(starts_raw, language),
            until=until,
        )

    if status == "pending_payment":
        return get_text(
            language,
            "settings_subscription_pending",
            plan=subscription.get("plan") or "Premium",
        )

    if status == "free_exhausted":
        return get_text(
            language,
            "settings_subscription_free_exhausted",
            used=used,
            limit=limit,
        )

    if status == "expired":
        return get_text(
            language,
            "settings_subscription_expired",
            plan=subscription.get("plan") or "Premium",
            until=_format_dt(subscription.get("expires_at"), language),
            used=used,
            limit=limit,
        )

    if status == "free":
        return get_text(
            language,
            "settings_subscription_free",
            used=used,
            limit=limit,
        )

    if user.get("is_premium"):
        until_raw = user.get("premium_until")
        until = "∞" if not until_raw else _format_dt(until_raw, language)
        return get_text(
            language,
            "settings_subscription_active",
            plan=user.get("premium_plan") or "Premium",
            starts=_format_dt(user.get("premium_starts_at"), language),
            until=until,
        )

    return get_text(
        language,
        "settings_subscription_free",
        used=used,
        limit=limit,
    )
