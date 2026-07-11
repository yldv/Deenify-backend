"""Uzbek Latin to Cyrillic transliteration for bot UI (uz_cy language)."""

import re

# Digraphs / special letters must run before single-char Y→Й mapping.
_MULTI_REPLACEMENTS = (
    ("Ng", "Нг"),
    ("NG", "НГ"),
    ("ng", "нг"),
    ("Sh", "Ш"),
    ("SH", "Ш"),
    ("sh", "ш"),
    ("Ch", "Ч"),
    ("CH", "Ч"),
    ("ch", "ч"),
    ("O‘", "Ў"),
    ("Oʻ", "Ў"),
    ("O'", "Ў"),
    ("o‘", "ў"),
    ("oʻ", "ў"),
    ("o'", "ў"),
    ("G‘", "Ғ"),
    ("Gʻ", "Ғ"),
    ("G'", "Ғ"),
    ("g‘", "ғ"),
    ("gʻ", "ғ"),
    ("g'", "ғ"),
    # Ye/Yo/Yu/Ya → Е/Ё/Ю/Я (not Йе/Йо/Йу/Йа)
    ("Ye", "Е"),
    ("YE", "Е"),
    ("ye", "е"),
    ("Yo", "Ё"),
    ("YO", "Ё"),
    ("yo", "ё"),
    ("Yu", "Ю"),
    ("YU", "Ю"),
    ("yu", "ю"),
    ("Ya", "Я"),
    ("YA", "Я"),
    ("ya", "я"),
)

_CHAR_MAP = {
    "A": "А",
    "B": "Б",
    "D": "Д",
    "E": "Е",
    "F": "Ф",
    "G": "Г",
    "H": "Ҳ",
    "I": "И",
    "J": "Ж",
    "K": "К",
    "L": "Л",
    "M": "М",
    "N": "Н",
    "O": "О",
    "P": "П",
    "Q": "Қ",
    "R": "Р",
    "S": "С",
    "T": "Т",
    "U": "У",
    "V": "В",
    "X": "Х",
    "Y": "Й",
    "Z": "З",
    "C": "С",
    "W": "В",
    "a": "а",
    "b": "б",
    "d": "д",
    "e": "е",
    "f": "ф",
    "g": "г",
    "h": "ҳ",
    "i": "и",
    "j": "ж",
    "k": "к",
    "l": "л",
    "m": "м",
    "n": "н",
    "o": "о",
    "p": "п",
    "q": "қ",
    "r": "р",
    "s": "с",
    "t": "т",
    "u": "у",
    "v": "в",
    "x": "х",
    "y": "й",
    "z": "з",
    "c": "с",
    "w": "в",
}

_CYRILLIC_RE = re.compile(r"[\u0400-\u04FF]")


def looks_cyrillic(text: str) -> bool:
    return bool(text and _CYRILLIC_RE.search(text))


def latin_to_cyrillic(text: str) -> str:
    if not text:
        return text
    if looks_cyrillic(text):
        return text
    result = text
    for latin, cyrillic in _MULTI_REPLACEMENTS:
        result = result.replace(latin, cyrillic)
    return "".join(_CHAR_MAP.get(char, char) for char in result)


def localize_quiz_content(question: dict, language: str) -> dict:
    """Bot uz_cy: API dan kelgan matn (yoki lotin fallback) → kirill."""
    if language != "uz_cy":
        return question
    localized = dict(question)
    localized["question"] = latin_to_cyrillic(question.get("question", ""))
    if question.get("description"):
        localized["description"] = latin_to_cyrillic(question.get("description", ""))
    localized["answers"] = [
        {
            "id": answer["id"],
            "text": latin_to_cyrillic(answer.get("text", "")),
        }
        for answer in question.get("answers", [])
    ]
    return localized


def localize_text(text: str, language: str) -> str:
    if language != "uz_cy" or not text:
        return text
    return latin_to_cyrillic(text)
