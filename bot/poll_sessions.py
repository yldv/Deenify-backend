"""In-memory map poll_id -> quiz context (FSM backup; cleared on bot restart)."""

from typing import Any

_sessions: dict[str, dict[str, Any]] = {}


def remember_poll(*, poll_id, question: dict, language: str, telegram_id: int) -> None:
    _sessions[str(poll_id)] = {
        "question": question,
        "language": language,
        "telegram_id": telegram_id,
    }


def get_poll_session(poll_id) -> dict[str, Any] | None:
    return _sessions.get(str(poll_id))


def forget_poll(poll_id) -> None:
    _sessions.pop(str(poll_id), None)
