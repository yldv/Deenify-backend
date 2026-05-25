from bot.uz_cyrillic import latin_to_cyrillic

TRANSLATION_LANGS = ("uz", "ru", "uz_cy")


def ensure_translations(translations: dict) -> dict:
    result = dict(translations)
    if "uz" in result and "uz_cy" not in result:
        result["uz_cy"] = latin_to_cyrillic(result["uz"])
    return result


def translated_defaults(model, values: dict) -> dict:
    defaults = {}
    field_names = {field.name for field in model._meta.get_fields()}
    for field, raw_translations in values.items():
        translations = ensure_translations(raw_translations)
        normal_value = translations.get("uz") or translations.get("ru") or ""
        if field in field_names:
            defaults[field] = normal_value
        for language in TRANSLATION_LANGS:
            value = translations.get(language)
            if value is None:
                continue
            translated_field = f"{field}_{language}"
            if translated_field in field_names:
                defaults[translated_field] = value
    return defaults
