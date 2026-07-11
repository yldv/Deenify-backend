"""Resolve quiz text with language fallbacks (uz / ru / uz_cy)."""

from django.utils.translation import get_language


def resolve_localized_text(obj, field_name: str, language: str | None = None) -> str:
    """Return the best non-empty translation for a model field.

    When ``language`` is set (or active via translation.override), prefer that
    language's field first so uz_cy from admin is not overwritten by Latin uz.
    """
    lang = (language or get_language() or "").replace("-", "_")
    preferred = []
    if lang:
        preferred.append(f"{field_name}_{lang}")
    preferred.extend(
        (
            field_name,
            f"{field_name}_uz",
            f"{field_name}_ru",
            f"{field_name}_uz_cy",
        )
    )

    seen = set()
    for name in preferred:
        if name in seen or not hasattr(obj, name):
            continue
        seen.add(name)
        value = (getattr(obj, name, None) or "").strip()
        if value:
            return value
    return ""


def count_poll_ready_answers(test) -> int:
    return sum(1 for answer in test.answers.all() if resolve_localized_text(answer, "text"))


def answers_with_empty_text(test):
    return [answer for answer in test.answers.all() if not resolve_localized_text(answer, "text")]


def is_test_poll_ready(test) -> bool:
    answers = list(test.answers.all())
    if len(answers) < 2:
        return False
    if not resolve_localized_text(test, "question"):
        return False
    return all(resolve_localized_text(answer, "text") for answer in answers)
