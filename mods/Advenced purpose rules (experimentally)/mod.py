"""Advenced purpose rules: назначение популярных плагинов по таблице rules.json."""
import re

PREFIX = re.compile(r"^(fruity|fabfilter|khs|kilohearts|unfiltered audio|waves)\s+")


def matches(name, known):
    """Имя начинается с записи таблицы, и дальше не продолжается буквой."""
    return name.startswith(known) and (len(name) == len(known) or not name[len(known)].isalpha())


def activate(api):
    """Подключает таблицу. Сначала длинные записи: "serumfx" важнее "serum"."""
    table = api.read_json("rules.json", {})
    ordered = sorted(table, key=len, reverse=True)

    def purpose(plugin):
        name = plugin.name.casefold()
        short = PREFIX.sub("", name)
        for known in ordered:
            if matches(name, known) or matches(short, known):
                return [table[known]]
        return None

    api.add_purpose_hook(purpose, priority=60)
