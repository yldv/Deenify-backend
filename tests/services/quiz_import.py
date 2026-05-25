import json
from typing import Any

from django.core.exceptions import ValidationError
from django.db import transaction

from tests.models import Answer, Test, TestCategory

from .translation_utils import translated_defaults

LEVEL_ALIASES = {
    "easy": Test.Level.EASY,
    "oson": Test.Level.EASY,
    "medium": Test.Level.MEDIUM,
    "orta": Test.Level.MEDIUM,
    "hard": Test.Level.HARD,
    "qiyin": Test.Level.HARD,
}


def parse_json_payload(raw: str | bytes) -> Any:
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValidationError(f"JSON noto'g'ri: {exc}") from exc


def normalize_import_payload(data: Any) -> dict:
    if isinstance(data, list):
        return {"questions": data}
    if not isinstance(data, dict):
        raise ValidationError("JSON obyekt yoki savollar ro'yxati bo'lishi kerak.")
    if "questions" not in data and "tests" in data:
        data = {**data, "questions": data["tests"]}
    if "questions" not in data:
        raise ValidationError("'questions' maydoni topilmadi.")
    return data


def normalize_level(value: str) -> str:
    key = (value or Test.Level.EASY).strip().lower()
    if key in LEVEL_ALIASES:
        return LEVEL_ALIASES[key]
    if key in Test.Level.values:
        return key
    raise ValidationError(f"Noto'g'ri daraja: {value}. easy / medium / hard")


def normalize_text_field(value: Any) -> dict:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        return {"uz": value, "ru": value}
    raise ValidationError("Matn uz/ru obyekt yoki qator bo'lishi kerak.")


def normalize_answers(raw_answers: list) -> list[tuple[bool, dict]]:
    if not raw_answers:
        raise ValidationError("Kamida bitta javob kerak.")
    normalized = []
    for item in raw_answers:
        if isinstance(item, dict):
            is_correct = bool(item.get("is_correct", item.get("correct", False)))
            text = normalize_text_field(item.get("text", item.get("answer", "")))
            normalized.append((is_correct, text))
            continue
        if isinstance(item, (list, tuple)) and len(item) >= 2:
            is_correct = bool(item[0])
            text = normalize_text_field(item[1])
            normalized.append((is_correct, text))
            continue
        raise ValidationError(
            "Javob formati: [true, {\"uz\": \"...\"}] yoki {\"is_correct\": true, \"text\": {...}}"
        )
    if not any(flag for flag, _ in normalized):
        raise ValidationError("Kamida bitta to'g'ri javob belgilang.")
    return normalized


def normalize_question(item: dict, index: int) -> dict:
    if not isinstance(item, dict):
        raise ValidationError(f"{index}-savol: obyekt bo'lishi kerak.")
    sort_order = item.get("sort_order", index)
    try:
        sort_order = int(sort_order)
    except (TypeError, ValueError) as exc:
        raise ValidationError(f"{index}-savol: sort_order raqam bo'lishi kerak.") from exc

    return {
        "sort_order": sort_order,
        "level": normalize_level(item.get("level", Test.Level.EASY)),
        "title": normalize_text_field(item.get("title", f"Savol {sort_order}")),
        "question": normalize_text_field(item.get("question", "")),
        "description": normalize_text_field(
            item.get("description", item.get("manba", ""))
        ),
        "explanation": normalize_text_field(item.get("explanation", "")),
        "answers": normalize_answers(item.get("answers", [])),
        "is_premium": bool(item.get("is_premium", False)),
    }


def get_or_create_category(slug: str | None) -> TestCategory:
    slug = (slug or "").strip() or TestCategory.get_default().slug
    category = TestCategory.objects.filter(slug=slug).first()
    if category:
        return category
    defaults = translated_defaults(
        TestCategory,
        {
            "name": {"uz": slug.title(), "ru": slug.title()},
            "description": {"uz": "", "ru": ""},
        },
    )
    category, _ = TestCategory.objects.get_or_create(
        slug=slug,
        defaults={**defaults, "is_active": True, "sort_order": 0},
    )
    return category


def upsert_test(category: TestCategory, item: dict) -> Test:
    defaults = {
        "category": category,
        "level": item["level"],
        "is_active": True,
        "is_premium": item["is_premium"],
        "sort_order": item["sort_order"],
        **translated_defaults(
            Test,
            {
                "title": item["title"],
                "question": item["question"],
                "description": item["description"],
                "explanation": item["explanation"],
            },
        ),
    }
    test, _ = Test.objects.update_or_create(
        category=category,
        level=item["level"],
        sort_order=item["sort_order"],
        defaults=defaults,
    )
    upsert_answers(test, item["answers"])
    return test


def upsert_answers(test: Test, answers: list[tuple[bool, dict]]) -> None:
    test.answers.update(is_correct=False)
    for index, (is_correct, text) in enumerate(answers, start=1):
        answer = test.answers.filter(sort_order=index).first()
        defaults = {
            "is_correct": is_correct,
            "sort_order": index,
            **translated_defaults(Answer, {"text": text}),
        }
        if answer:
            for field, value in defaults.items():
                setattr(answer, field, value)
            answer.save(update_fields=tuple(defaults.keys()) + ("updated_at",))
        else:
            Answer.objects.create(test=test, **defaults)


@transaction.atomic
def import_questions_from_payload(
    data: Any,
    *,
    category_slug: str | None = None,
    deactivate_others: bool = False,
) -> dict:
    payload = normalize_import_payload(data)
    slug = category_slug or payload.get("category_slug") or payload.get("category")
    category = get_or_create_category(slug)

    if deactivate_others or payload.get("deactivate_others"):
        Test.objects.filter(category=category).update(is_active=False)

    questions_raw = payload.get("questions", [])
    if not questions_raw:
        raise ValidationError("Savollar ro'yxati bo'sh.")

    imported = 0
    for index, raw_item in enumerate(questions_raw, start=1):
        item = normalize_question(raw_item, index)
        if not item["question"].get("uz") and not item["question"].get("ru"):
            raise ValidationError(f"{index}-savol: savol matni bo'sh.")
        upsert_test(category, item)
        imported += 1

    active_count = Test.objects.filter(category=category, is_active=True).count()
    return {
        "imported": imported,
        "category": category.slug,
        "active_questions": active_count,
    }
