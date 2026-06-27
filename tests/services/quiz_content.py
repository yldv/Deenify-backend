"""Resolve quiz text with language fallbacks (uz / ru / uz_cy)."""


def resolve_localized_text(obj, field_name: str) -> str:
    """Return the first non-empty translation for a model field."""
    candidates = (
        field_name,
        f"{field_name}_uz",
        f"{field_name}_ru",
        f"{field_name}_uz_cy",
    )
    for name in candidates:
        if not hasattr(obj, name):
            continue
        value = (getattr(obj, name, None) or "").strip()
        if value:
            return value
    return ""


def count_poll_ready_answers(test) -> int:
    return sum(1 for answer in test.answers.all() if resolve_localized_text(answer, "text"))


def is_test_poll_ready(test) -> bool:
    if not resolve_localized_text(test, "question"):
        return False
    return count_poll_ready_answers(test) >= 2
