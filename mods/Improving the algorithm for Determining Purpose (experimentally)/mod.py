"""Improving the algorithm: более тонкие назначения и обучение на действиях пользователя."""
import os
import re

import i18n
import rules

PURPOSES = {
    "saturation": {"EN-en": "Saturation", "RU-ru": "Сатурация"},
    "transient": {"EN-en": "Transient shapers", "RU-ru": "Транзиент-шейперы"},
    "algo_reverb": {"EN-en": "Algorithmic reverbs", "RU-ru": "Алгоритмические ревербы"},
    "convolution": {"EN-en": "Convolution reverbs", "RU-ru": "Конволюционные ревербы"},
    "compressor": {"EN-en": "Compressors", "RU-ru": "Компрессоры"},
    "limiter": {"EN-en": "Limiters", "RU-ru": "Лимитеры"},
}
# Слова в имени, проверяются по порядку: только для эффектов.
WORDS = tuple((purpose, re.compile(pattern)) for purpose, pattern in (
    ("transient", r"transient|\bkickstart\b|\bpunch\b|envelope shaper"),
    ("saturation", r"saturat|\btape\b|\btube\b|\bwarm|decapitator|saturn|\bheat\b"),
    ("convolution", r"convol|\bimpulse\b|\bir\b|altiverb|\bspace designer\b"),
    ("algo_reverb", r"valhalla|reverb|\bverb\b|\bplate\b|\bhall\b|\broom\b|lexicon|blackhole"),
    ("limiter", r"\blimit|maximi[sz]|\bl[123]\b|pro-l"),
    ("compressor", r"compress|\bcomp\b|\b1176\b|\bla-?2a\b|cla-|pro-c|\bglue\b"),
))
BUTTON = {"EN-en": "Forget what was learned", "RU-ru": "Забыть выученное"}


def family(plugin):
    """Семейство плагина: производитель и первое слово имени."""
    words = re.findall(r"[^\W\d_]+", plugin.name.casefold())
    return f"{plugin.raw_vendor.casefold()}|{words[0] if words else ''}"


def activate(api):
    """Подключает назначения, распознавание и обучение."""
    for purpose_id, labels in PURPOSES.items():
        api.add_purpose(purpose_id, labels)
    data = api.load_data({}) or {}
    learned = data.setdefault("families", {})

    def purpose(plugin):
        known = learned.get(family(plugin))
        if known in rules.PURPOSES:
            return [known]
        if plugin.kind == "Effects":
            name = plugin.name.casefold()
            for purpose_id, pattern in WORDS:
                if pattern.search(name):
                    return [purpose_id]
        return None

    def changed(plugins, chosen):
        """Запоминает ручной выбор; снятый выбор забывается."""
        for plugin in plugins:
            if chosen:
                learned[family(plugin)] = chosen
            else:
                learned.pop(family(plugin), None)
        api.save_data(data)

    def loaded(plugins):
        """Плагин лежит в папке с названием назначения: значит, пользователь так решил."""
        names = {}
        for purpose_id in rules.PURPOSES:
            names[rules.purpose_label(purpose_id).casefold()] = purpose_id
            names[i18n.tr_in("EN-en", rules.PURPOSES[purpose_id]).casefold()] = purpose_id
        fresh = False
        for plugin in plugins:
            if plugin.organized_in and plugin.purpose_source not in ("manual", "rule"):
                found = names.get(os.path.basename(plugin.organized_in.rstrip("\\/")).casefold())
                if found and found != "other" and found not in plugin.purposes and learned.get(family(plugin)) != found:
                    learned[family(plugin)] = found
                    fresh = True
        if fresh:
            api.save_data(data)
        return fresh

    def forget():
        learned.clear()
        api.save_data(data)
        api.app.refresh()

    api.add_purpose_hook(purpose, priority=20)
    api.on_purpose_changed(changed)
    api.on_load(loaded)
    api.add_action(BUTTON, forget)
