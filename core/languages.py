from core.constants import DEFAULT_LANGUAGE, SUPPORTED_LANGUAGES


def normalize_language_code(raw: str | None) -> str:
    """Accept uz, uz_cy, ru from header or user profile."""
    if not raw:
        return DEFAULT_LANGUAGE
    code = raw.strip().split(",", 1)[0].strip().lower().replace("-", "_")
    if code in SUPPORTED_LANGUAGES:
        return code
    return DEFAULT_LANGUAGE
