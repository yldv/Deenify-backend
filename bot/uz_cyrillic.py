"""Uzbek Latin to Cyrillic transliteration for bot UI (uz_cy language)."""

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
    ("O'", "Ў"),
    ("o‘", "ў"),
    ("o'", "ў"),
    ("G‘", "Ғ"),
    ("G'", "Ғ"),
    ("g‘", "ғ"),
    ("g'", "ғ"),
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


def latin_to_cyrillic(text: str) -> str:
    if not text:
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
    if question.get("explanation"):
        localized["explanation"] = latin_to_cyrillic(question.get("explanation", ""))
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
