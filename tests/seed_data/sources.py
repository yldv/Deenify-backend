def manba_description(bob: int, bet: int) -> dict[str, str]:
    """Poll explanation text — same source on all three languages (uz / uz_cy / ru)."""
    return {
        "uz": (
            "📚 Manba: Mo'minning Me'roji (Mufassal Namoz Kitobi, {bob} bob, {bet} bet)\n\n"
            "✍️ Muallif: Shayx Muhammad Sodiq Muhammad Yusuf"
        ).format(bob=bob, bet=bet),
        "uz_cy": (
            "📚 Манба: Мўминнинг Меърожи (Муфассал намоз китоби, {bob} боб, {bet} бет)\n\n"
            "✍️ Муаллиф: Шайх Муҳаммад Соддиқ Муҳаммад Юсуф"
        ).format(bob=bob, bet=bet),
        "ru": (
            "📚 Источник: Mo'minning Me'roji (Подробная книга намаза, {bob} гл., {bet} стр.)\n\n"
            "✍️ Автор: шейх Муҳаммад Соддиқ Муҳаммад Юсуф"
        ).format(bob=bob, bet=bet),
    }
