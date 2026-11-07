"""Сортировка и фильтры: для чего плагин, куда он ляжет и подходит ли он под фильтр.

Три независимые части, все управляются данными:

* classify() определяет назначение плагина по цепочке источников.
* Раскладка: шаблон папок, например "{vendor}\\{purpose}" или "{purpose}\\{vendor}".
* Query: фильтр из текста и условий по полям, со счётчиками для меню фильтров.
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, field

import i18n
from i18n import tr, tr_in

# --------------------------------------------------------------------------------------------
# Назначения. В настройках хранится id; подпись видит пользователь, ею же называются папки.
# --------------------------------------------------------------------------------------------
PURPOSES = {
    "synth": "Синтезаторы", "drums": "Драмы", "sampler": "Сэмплеры", "instrument": "Инструменты",
    "dynamics": "Динамика", "eq": "Эквалайзеры", "filter": "Фильтры", "reverb": "Реверберация", "delay": "Дилеи",
    "modulation": "Модуляция", "distortion": "Дисторшн и сатурация", "pitch": "Высота тона", "vocal": "Вокал",
    "stereo": "Стерео и пространство", "channel": "Канальные линейки", "mastering": "Мастеринг",
    "restoration": "Реставрация", "analyzer": "Анализаторы", "creative": "Креативные эффекты",
    "controller": "Контроллеры и MIDI", "utility": "Утилиты", "other": "Прочее",
}
INSTRUMENT_PURPOSES = {"synth", "drums", "sampler", "instrument"}


EXTRA_LABELS: dict[str, dict] = {}  # подписи назначений, которые добавили моды


def add_purpose(purpose_id: str, labels: dict) -> None:
    """Добавляет назначение из мода. labels: подписи по кодам языков."""
    PURPOSES[purpose_id] = labels.get("RU-ru") or labels["EN-en"]
    EXTRA_LABELS[purpose_id] = labels


def remove_purpose(purpose_id: str) -> None:
    """Убирает назначение выключенного мода."""
    PURPOSES.pop(purpose_id, None)
    EXTRA_LABELS.pop(purpose_id, None)


def _label_in(language: str, purpose_id: str) -> str:
    """Название назначения на заданном языке. Пустой язык значит язык интерфейса."""
    extra = EXTRA_LABELS.get(purpose_id)
    if extra:
        return extra.get(language or i18n.LANG) or extra["EN-en"]
    return tr_in(language, PURPOSES.get(purpose_id, purpose_id))


def purpose_label(purpose_id: str) -> str:
    """Название назначения на языке интерфейса."""
    extra = EXTRA_LABELS.get(purpose_id)
    if extra:
        return _label_in("", purpose_id)
    return tr(PURPOSES.get(purpose_id, PURPOSES["other"]))


# Категории из метаданных VST3 и VST2. "Effect" и "Fx" ничего конкретного не значат.
CATEGORY_MAP = {
    "dynamics": "dynamics", "eq": "eq", "filter": "filter", "reverb": "reverb", "room fx": "reverb", "delay": "delay",
    "modulation": "modulation", "distortion": "distortion", "pitch shift": "pitch", "mastering": "mastering",
    "restoration": "restoration", "analyzer": "analyzer", "analysis": "analyzer", "spatial": "stereo", "surround": "stereo",
    "spacializer": "stereo", "ambisonics": "stereo", "tools": "utility", "network": "utility", "channel strip": "channel",
    "synth": "synth", "instrument synth": "synth", "sampler": "sampler", "drum": "drums", "external": "utility",
}

# Имена, по словам которых назначение не понять. Запись совпадает с целыми словами в начале имени,
# поэтому "ace" не поймает "Acer"; * в конце допускает продолжение, как в ValhallaPlate.
KNOWN_NAMES = {
    "ott": "dynamics", "soundgoodizer": "dynamics", "maximus": "mastering", "kickstart": "dynamics", "squashit": "dynamics",
    "presswerk": "dynamics", "slammer": "dynamics", "kuvert": "dynamics", "punch 1": "dynamics", "elysia alpha": "mastering",
    "elysia mpressor": "dynamics", "elysia nvelope": "dynamics", "elysia museq": "eq", "elysia niveau": "eq", "lindell sbc": "dynamics",
    "lindell 50": "channel", "lindell channelx": "channel", "sausage fattener": "distortion", "camelcrusher": "distortion",
    "ohmicide": "distortion", "saturn": "distortion", "satin": "distortion", "faturator": "distortion", "needlepoint": "distortion",
    "degrader": "distortion", "reamp": "distortion", "freeamp": "distortion", "richter": "distortion", "fosfat": "distortion",
    "knorr": "distortion", "daw cassette": "distortion", "daw lp": "distortion", "tape mello": "distortion",
    "pro-q": "eq", "gotoeq": "eq", "carve eq": "eq", "slice eq": "eq", "fabfilter volcano": "filter", "filtershaper": "filter",
    "djmfilter": "filter", "bassfocus": "eq", "bass mint": "eq", "low lifter": "eq", "uhbik-q": "eq", "uhbik-f": "filter",
    "uhbik-a": "reverb", "uhbik-d": "delay", "uhbik-g": "modulation", "uhbik-p": "modulation", "uhbik-s": "pitch", "uhbik-t": "modulation",
    "valhalla*": "reverb", "valhallaubermod": "modulation", "zebra*": "synth",
    "pro-c": "dynamics", "pro-ds": "vocal", "pro-g": "dynamics", "pro-l": "mastering", "pro-mb": "dynamics", "pro-r": "reverb",
    "timeless": "delay", "volcano": "filter", "simplon": "filter", "micro": "filter", "minimeters*": "analyzer",
    "xvox comp": "vocal", "xvox ds": "vocal", "xvox pro": "vocal", "xvox sfx": "vocal", "xvox space": "vocal", "xvox tone": "vocal",
    "emphasis": "mastering", "emphasizer": "mastering", "frequency splitter": "utility", "fruity lsd": "utility",
    "fruity scratcher": "creative", "fruity wrapper": "utility", "hardcore": "distortion", "multiband x6": "dynamics",
    "efx refract": "creative", "reason rack": "utility", "khs reverser": "creative", "khs tape stop": "creative", "dblue.tapestop": "creative", "zrev": "reverb", "kleverb": "reverb", "r0verb": "reverb", "rum": "reverb",
    "walls": "reverb", "wormhole": "creative", "stage": "reverb", "space in-your-face": "reverb", "luxeverb": "reverb",
    "colourcopy": "delay", "gaffel": "delay", "modley": "delay", "parrot": "delay", "spinn": "modulation", "revolv": "modulation",
    "disperser": "creative", "shaperbox": "creative", "snap heap": "creative", "multipass": "creative", "effector": "creative",
    "infiltrator": "creative", "gross beat": "creative", "newtime": "pitch", "newtone": "pitch", "pitcher": "vocal",
    "melodyne": "vocal", "auto-tune": "vocal", "auto-key": "pitch", "goyo": "vocal", "humanoid": "vocal", "dehumaniser": "vocal",
    "pitchmap": "pitch", "morph": "creative", "brusfri": "restoration", "unchirp": "restoration", "unfilter": "restoration",
    "unveil": "restoration", "unmix": "restoration", "balance 1": "mastering", "intensity": "mastering", "loud 1": "mastering",
    "grand finale": "mastering", "hawkeye": "analyzer", "spl hawkeye": "analyzer", "adptr metricab": "analyzer", "adptr streamliner": "mastering",
    "adptr sculpt": "dynamics", "wave candy": "analyzer", "tuner": "analyzer", "edison": "utility", "patcher": "utility",
    "wide": "stereo", "haaze": "reverb", "pana": "stereo", "dimension expander": "stereo", "wide awake": "stereo", "schoeps": "stereo",
    "kepler": "delay", "serum": "synth", "serumfx": "creative", "vital": "synth", "phase plant": "synth", "diva": "synth", "hive": "synth",
    "zebrify": "creative", "bazille": "synth", "ace": "synth", "repro": "synth", "sytrus": "synth", "harmor": "synth",
    "harmless": "synth", "poizone": "synth", "sakura": "synth", "sawer": "synth", "toxic biohazard": "synth", "morphine": "synth",
    "transistor bass": "synth", "boobass": "synth", "simsynth": "synth", "minisynth": "synth", "wedge force": "synth", "xils": "synth",
    "fabfilter one": "synth", "fabfilter twin": "synth", "fabfilter simplon": "filter", "fabfilter micro": "filter", "reaktor": "synth",
    "op-1drumutil": "drums", "ogun": "synth", "plucked": "instrument", "elpiano": "instrument", "fl keys": "instrument", "fl slayer": "instrument",
    "ample guitar": "instrument", "virtual pianist": "instrument", "speldosa": "instrument", "borsta": "drums", "skaka": "drums", "tomofon": "drums",
    "directwave": "sampler", "flex": "sampler", "slicex": "sampler", "fpc": "drums", "fruity slicer": "sampler", "soundfont": "sampler",
    "fruity granulizer": "sampler", "oneshot": "sampler", "hillman": "instrument", "stark": "dynamics", "esspresso": "vocal",
    "korvpressor": "dynamics", "ting": "creative", "luxe": "creative", "fl studio vsti": "utility", "fl studio mobile": "instrument",
    "vott": "vocal", "twangstrom": "distortion", "runciter": "distortion", "mfm2": "delay", "duck": "dynamics", "texture": "creative",
    "tantra": "creative", "tails": "reverb", "silo": "creative", "specops": "creative", "deltamodulator": "creative", "endless smile": "creative",
    "eternal return": "delay", "snapback": "drums", "orange vocoder": "vocal", "fiedler audio": "stereo", "metricab": "analyzer",
}
_KNOWN_ORDERED = sorted(KNOWN_NAMES, key=len, reverse=True)

# Слова в имени плагина, проверяются по порядку. Инструментальные только для генераторов.
_EFFECT_WORDS = (
    ("vocal", r"vocal|vocod|voice|de-?ess|tuner\b"),
    ("restoration", r"de-?noise|de-?click|de-?hum|restor|repair"),
    ("mastering", r"master|maximi[sz]|loudness"),
    ("analyzer", r"\bmeter|analy[sz]|spectro|scope|\bdb meter|\bmetering"),
    ("reverb", r"reverb|reeverb|\bverb|convol|\broom\b|\bplate\b|\bhall\b"),
    ("delay", r"delay|echo"),
    ("eq", r"\beq\b|equo|equali[sz]|\b\d+-band|\bbass boost|parametric"),
    ("filter", r"filter|philter|\bladder\b|\bformant\b|\blp\b|\bhp\b|resonator"),
    ("dynamics", r"compress|compact|limit|\bgate\b|transient|expander|dynamic|squeeze|ducker|\bduck\b|\bglue\b|sidechain"),
    ("distortion", r"distort|distructor|overdrive|saturat|clipper|\bclip\b|bitcrush|crusher|waveshap|\bshaper\b|\bdist\b|\bfuzz"),
    ("modulation", r"chorus|flang|phaser|tremolo|vibrato|ensemble|ring mod|\bpan\b|panomatic|rotary"),
    ("pitch", r"pitch|frequency shift|harmoni[sz]"),
    ("stereo", r"stereo|\bhaas\b|\bwide\b|widen|spread|\bcenter\b|phase inverter|upmix|\bbalance\b"),
    ("channel", r"channel strip|channel mixer|\bchannel\b"),
    ("controller", r"control|midi|\bvfx\b|\bkeyboard\b|\bx-y\b"),
    ("utility", r"\bgain\b|\bmute\b|\bsend\b|notebook|clock|\bvideo\b|rewired|visuali[sz]|dashboard|transporter|transmitter|razer|bridge"),
)
_INSTRUMENT_WORDS = (
    ("drums", r"drum|\bkick\b|\b808\b|\bsnare\b|percuss|beat|autogun"),
    ("sampler", r"sampl|slice|sf2|soundfont"),
    ("instrument", r"piano|keys\b|guitar|\bbass\b|string|organ|flute|\bbrass\b"),
    ("controller", r"control|midi|\bvfx\b|dashboard|\bpatcher\b"),
    ("synth", r"synth|\bosc\b|\bpoly\b|\bfm\b|wavetable"),
)
_EFFECT_RE = tuple((pid, re.compile(pattern)) for pid, pattern in _EFFECT_WORDS)
_INSTRUMENT_RE = tuple((pid, re.compile(pattern)) for pid, pattern in _INSTRUMENT_WORDS)


@dataclass(slots=True)
class Rule:
    """Правило пользователя: должны совпасть все непустые условия, побеждает первое подошедшее."""
    purpose: str
    name: str = ""  # регулярное выражение для имени, без учёта регистра
    vendor: str = ""  # регулярное выражение для производителя, без учёта регистра
    kind: str = ""  # Effects или Generators

    def matches(self, plugin) -> bool:
        """Подходит ли плагин под правило."""
        if self.kind and plugin.kind != self.kind:
            return False
        try:
            if self.name and not re.search(self.name, plugin.name, re.I):
                return False
            if self.vendor and not re.search(self.vendor, plugin.vendor, re.I):
                return False
        except re.error:
            return False  # ошибка в шаблоне отключает только это правило
        return bool(self.name or self.vendor or self.kind)


def load_rules(raw: list | None) -> list[Rule]:
    """Превращает правила из настроек в объекты Rule, пропуская неверные."""
    rules = []
    for item in raw or []:
        if isinstance(item, dict) and item.get("purpose") in PURPOSES:
            rules.append(Rule(item["purpose"], str(item.get("name", "")), str(item.get("vendor", "")), str(item.get("kind", ""))))
    return rules


def _from_categories(plugin) -> list[str]:
    """Назначения из категорий, которые заявил плагин."""
    found: list[str] = []
    for item in plugin.files:
        for token in item.category.split("|"):
            purpose = CATEGORY_MAP.get(token.strip().casefold())
            if purpose and purpose not in found:
                found.append(purpose)
    return found


def _known_match(name: str, known: str) -> bool:
    """Совпадает ли имя плагина с записью справочника."""
    if known.endswith("*"):
        return name.startswith(known[:-1])
    if not name.startswith(known):
        return False
    return len(name) == len(known) or not name[len(known)].isalpha()


def classify(plugin, overrides: dict | None = None, rules: list[Rule] | None = None, hooks=()) -> tuple[list[str], str]:
    """Возвращает (назначения, источник). Первое назначение выбирает папку, все участвуют в фильтрах.

    hooks: обработчики модов. Ручной выбор и правила пользователя важнее них.
    """
    forced = (overrides or {}).get(plugin.name_id)
    if forced in PURPOSES:
        return [forced], "manual"
    for rule in rules or ():
        if rule.matches(plugin):
            return [rule.purpose], "rule"
    for hook in hooks:
        answer = hook(plugin)
        if answer:
            return list(answer), "mod"
    name = plugin.name.casefold()
    # Сначала длинные записи: "valhallaubermod" важнее "valhalla", "serumfx" важнее "serum".
    stripped = re.sub(r"^(fruity|fabfilter|khs|kilohearts|unfiltered audio)\s+", "", name)
    for known in _KNOWN_ORDERED:
        if _known_match(name, known) or _known_match(stripped, known):
            return [KNOWN_NAMES[known]], "name"
    words = _INSTRUMENT_RE if plugin.kind == "Generators" else _EFFECT_RE
    categories = _from_categories(plugin)
    # Если в имени есть "Reverb", это реверб, какую бы общую категорию ни указал производитель.
    if plugin.kind == "Effects" and len(categories) < 3:
        for purpose, pattern in words:
            if pattern.search(name):
                return [purpose, *[c for c in categories if c != purpose]], "keyword"
    if categories:
        specific = [c for c in categories if c != "synth"] if plugin.kind == "Effects" else categories
        if len(specific) >= 3:  # много заявленных задач: это мультиэффект
            return ["creative", *specific], "category"
        if specific:
            return specific, "category"
    for purpose, pattern in words:
        if pattern.search(name):
            return [purpose], "keyword"
    if plugin.kind == "Generators":
        return ["synth"], "fallback"
    return ["other"], "fallback"


# --------------------------------------------------------------------------------------------
# Раскладки папок
# --------------------------------------------------------------------------------------------
LAYOUTS = {
    "vendor": "{vendor}",
    "purpose": "{purpose}",
    "vendor_purpose": "{vendor}\\{purpose}",
    "purpose_vendor": "{purpose}\\{vendor}",
    "format_vendor": "{format}\\{vendor}",
    "format_purpose": "{format}\\{purpose}",
    "letter": "{letter}",
    "user_vendor": "USER\\{vendor}",
    "user_purpose_vendor": "USER\\{purpose}\\{vendor}",
}
LAYOUT_LABELS = {
    "vendor": "Производитель", "purpose": "Назначение", "vendor_purpose": "Производитель \\ Назначение",
    "purpose_vendor": "Назначение \\ Производитель", "format_vendor": "Формат \\ Производитель",
    "format_purpose": "Формат \\ Назначение", "letter": "По первой букве", "user_vendor": "USER \\ Производитель",
    "user_purpose_vendor": "USER \\ Назначение \\ Производитель",
}
TOKENS = ("vendor", "purpose", "format", "bits", "letter", "kind")
_TOKEN = re.compile(r"{(\w+)}")
_LEGAL_SUFFIX = re.compile(r"[,\s]+(?:llc|l\.l\.c\.|inc\.?|ltd\.?|limited|gmbh|ag|corp\.?|corporation|co\.?|sarl|s\.a\.r\.l\.|pty)\s*$", re.I)


def layout_tokens(template: str) -> dict[str, str]:
    """Проверяет шаблон. Возвращает найденные проблемы; {} значит, что шаблон годится."""
    problems = {}
    unknown = [t for t in _TOKEN.findall(template) if t not in TOKENS]
    if unknown:
        problems["unknown"] = ", ".join(unknown)
    if not template.strip(" \\/"):
        problems["empty"] = "1"
    return problems


def clean_vendor(vendor: str) -> str:
    """Убирает из имени производителя юридические хвосты вроде LLC или GmbH."""
    original, previous = vendor, None
    while previous != vendor:
        previous = vendor
        vendor = _LEGAL_SUFFIX.sub("", vendor).rstrip(" ,")
    return vendor or original


def apply_alias(vendor: str, aliases: dict[str, str]) -> str:
    """aliases: {производитель в нижнем регистре: имя, которое показывать}."""
    return aliases.get(vendor.casefold(), vendor)


def layout_parts(template: str, plugin, language: str = "", strip_suffix: bool = False) -> list[str]:
    """Подставляет данные плагина в шаблон. Возвращает уровни папок, ещё не очищенные."""
    primary = plugin.primary
    purpose = plugin.purposes[0] if plugin.purposes else "other"
    values = {
        "vendor": clean_vendor(plugin.vendor) if strip_suffix else plugin.vendor,
        "purpose": _label_in(language, purpose),
        "format": primary.format if primary else "", "bits": primary.bits if primary else "",
        "letter": _first_letter(plugin.name), "kind": plugin.kind,
    }
    parts = []
    for level in re.split(r"[\\/]+", template):
        text = _TOKEN.sub(lambda m: values.get(m.group(1), ""), level).strip()
        if text:
            parts.append(text)
    return parts


def _first_letter(name: str) -> str:
    """Первая буква имени, 0-9 для цифр, # для остального."""
    for char in name:
        if char.isalpha():
            return char.upper()
        if char.isdigit():
            return "0-9"
    return "#"


# --------------------------------------------------------------------------------------------
# Фильтры. Поле выдаёт значения плагина для сравнения. Новый фильтр: новая запись здесь.
# --------------------------------------------------------------------------------------------
DAY = 86400.0


def _purposes(p):
    """Назначения плагина для фильтра."""
    return tuple(p.purposes)


def _age_buckets(p):
    """В какие периоды давности попадает файл плагина."""
    if not p.installed:
        return ()
    age = (time.time() - p.installed) / DAY
    return tuple(label for label, days in (("7d", 7), ("30d", 30), ("90d", 90), ("365d", 365)) if age <= days)


def _size_bucket(p):
    """Группа размера файла."""
    mb = p.size / 1048576
    if not p.size:
        return ()
    return ("small",) if mb < 10 else ("medium",) if mb < 100 else ("large",)


FIELDS = {
    "purpose": _purposes,
    "vendor": lambda p: (p.vendor,),
    "format": lambda p: tuple(f.format for f in p.files if f.format),
    "kind": lambda p: (p.kind,),
    "bits": lambda p: tuple(f.bits for f in p.files if f.bits),
    "status": lambda p: ("ok" if p.ok else "error",),
    "organized": lambda p: ("yes" if p.organized_in else "no",),
    "source": lambda p: (p.purpose_source,),
    "formats_count": lambda p: ("multi" if len({f.format for f in p.files}) > 1 else "single",),
    "edited": lambda p: ("yes" if p.vendor_edited else "no",),
    "age": _age_buckets,
    "size": _size_bucket,
    "name": lambda p: (p.name,),
    "folder": lambda p: (p.organized_in or "",),
    "category": lambda p: tuple(t for f in p.files for t in f.category.split("|") if t),
}
ALIASES = {
    "назначение": "purpose", "для": "purpose", "вендор": "vendor", "производитель": "vendor", "формат": "format", "тип": "kind",
    "бит": "bits", "статус": "status", "организован": "organized", "источник": "source", "возраст": "age", "размер": "size",
    "имя": "name", "папка": "folder", "категория": "category", "форматов": "formats_count", "изменён": "edited",
}
_VALUE_ALIASES = {
    "kind": {"effect": "effects", "fx": "effects", "эффект": "effects", "эффекты": "effects", "synth": "generators",
             "synths": "generators", "generator": "generators", "синт": "generators", "синты": "generators", "генератор": "generators", "генераторы": "generators"},
    "organized": {"да": "yes", "нет": "no", "true": "yes", "false": "no"},
    "status": {"ошибка": "error", "ошибки": "error", "errors": "error"},
}
_EXACT_FIELDS = {"format", "bits", "kind", "status", "organized", "source", "formats_count", "edited", "age", "size"}
_QUERY_TOKEN = re.compile(r'(-)?(?:([^\s:"]+):)?(?:"([^"]*)"|(\S+))')


@dataclass(slots=True)
class Condition:
    """Одно условие запроса: поле, значения и отрицание."""
    field: str
    values: tuple[str, ...]
    negate: bool = False


@dataclass(slots=True)
class Query:
    """Готовый фильтр: текст И условия И выбор в меню (внутри одной группы подходит любое значение)."""
    text: list[tuple[str, bool]] = field(default_factory=list)
    conditions: list[Condition] = field(default_factory=list)

    def matches(self, plugin, selections: dict | None = None, skip: str | None = None) -> bool:
        """Подходит ли плагин. skip: группа меню, которую не надо учитывать."""
        for word, negate in self.text:
            if (word in plugin.search) == negate:
                return False
        for condition in self.conditions:
            if not _condition_matches(condition, plugin):
                return False
        for name, chosen in (selections or {}).items():
            if name != skip and chosen and not (set(FIELDS[name](plugin)) & set(chosen)):
                return False
        return True


def _condition_matches(condition: Condition, plugin) -> bool:
    """Проверяет одно условие запроса."""
    values = [str(v).casefold() for v in FIELDS[condition.field](plugin)]
    if condition.field == "purpose":
        values += [purpose_label(v).casefold() for v in plugin.purposes]
    aliases = _VALUE_ALIASES.get(condition.field, {})
    wanted = [aliases.get(item, item) for item in condition.values]
    if condition.field in _EXACT_FIELDS:  # format:vst не должен находить VST3
        hit = any(item == value for item in wanted for value in values)
    else:
        hit = any(item in value for item in wanted for value in values)
    return hit != condition.negate


def parse_query(text: str) -> Query:
    """Понимает слова, "фразы", -исключения, поле:значение и поле:одно,другое.

    Пример: purpose:reverb,delay vendor:"plugin alliance" -format:vst organized:no
    """
    query = Query()
    for match in _QUERY_TOKEN.finditer(text.casefold()):
        minus, name, quoted, plain = match.groups()
        value = quoted if quoted is not None else plain
        if not value:
            continue
        name = ALIASES.get(name, name)
        if name in FIELDS:
            values = tuple(v for v in value.split(",") if v)
            if values:
                query.conditions.append(Condition(name, values, bool(minus)))
        else:
            word = f"{name}:{value}" if name else value
            query.text.append((word, bool(minus)))
    return query


def facet_counts(plugins, field_name: str, query: Query, selections: dict | None = None) -> dict[str, int]:
    """Считает значения одной группы фильтров с учётом всех остальных, для меню."""
    getter = FIELDS[field_name]
    counts: dict[str, int] = {}
    for plugin in plugins:
        if query.matches(plugin, selections, skip=field_name):
            for value in set(getter(plugin)):
                counts[value] = counts.get(value, 0) + 1
    return counts
