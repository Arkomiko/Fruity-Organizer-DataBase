"""Язык интерфейса. Исходные строки русские; language/<код>.json сопоставляет им перевод.

Папка language рядом с программой важнее встроенной, поэтому перевод можно поправить без пересборки.
"""
from __future__ import annotations

import ctypes
import json
import os
import sys
from functools import lru_cache

DEFAULT = "EN-en"
# Основной код языка Windows -> файл языка.
_WINDOWS_LANGUAGES = {
    0x09: "EN-en", 0x19: "RU-ru", 0x23: "RU-ru", 0x04: "ZH-cn", 0x0A: "ES-es", 0x39: "HI-in", 0x01: "AR-sa", 0x0C: "FR-fr",
    0x45: "BN-bd", 0x16: "PT-br", 0x20: "UR-pk", 0x21: "ID-id", 0x07: "DE-de", 0x11: "JA-jp", 0x1F: "TR-tr", 0x12: "KO-kr",
    0x2A: "VI-vn", 0x10: "IT-it", 0x15: "PL-pl", 0x22: "UK-ua", 0x1E: "TH-th",
}
_SHORT = {"ru": "RU-ru", "en": "EN-en"}

LANG = "RU-ru"
_table: dict[str, str] = {}
_plural_rule = "slavic"
_other: dict[str, dict] = {}


def _folders() -> list[str]:
    """Папки, где искать файлы языков, по порядку важности."""
    here = os.path.dirname(os.path.abspath(__file__))
    folders = [os.path.join(os.path.dirname(here), "language")]
    if getattr(sys, "frozen", False):
        folders = [os.path.join(os.path.dirname(sys.executable), "language"), os.path.join(getattr(sys, "_MEIPASS", ""), "language")]
    return folders


def _read(code: str) -> dict | None:
    """Читает файл языка. None, если его нет или он повреждён."""
    for folder in _folders():
        try:
            with open(os.path.join(folder, code + ".json"), encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                return data
        except (OSError, ValueError):
            continue
    return None


EN = {k: v for k, v in (_read("EN-en") or {}).items() if k != "_meta"}


@lru_cache(maxsize=1)
def available() -> dict[str, str]:
    """Все найденные языки: {код: название на этом языке}."""
    codes = set()
    for folder in _folders():
        try:
            codes.update(n[:-5] for n in os.listdir(folder) if n.endswith(".json"))
        except OSError:
            pass
    result = {}
    for code in codes:
        data = _read(code)
        if data:
            result[code] = data.get("_meta", {}).get("name", code)
    return dict(sorted(result.items(), key=lambda kv: kv[1].casefold()))


def detect_language() -> str:
    """Язык интерфейса Windows, а если он не поддерживается, английский."""
    try:
        primary = ctypes.windll.kernel32.GetUserDefaultUILanguage() & 0x3FF
    except (OSError, AttributeError):
        return DEFAULT
    return _WINDOWS_LANGUAGES.get(primary, DEFAULT)


def set_language(lang: str | None) -> None:
    """Выбирает язык интерфейса. Пустое значение: язык Windows."""
    global LANG, _table, _plural_rule
    code = _SHORT.get(lang, lang) if lang else detect_language()
    data = _read(code)
    if data is None:
        code, data = DEFAULT, _read(DEFAULT) or {}
    LANG = code
    _plural_rule = data.get("_meta", {}).get("plural", "simple")
    _table = {k: v for k, v in data.items() if k != "_meta"}


def tr(text: str) -> str:
    """Переводит строку. Если перевода нет, берёт английскую версию."""
    return _table.get(text) or EN.get(text) or text


def tr_in(code: str, text: str) -> str:
    """Переводит на другой язык, не меняя язык интерфейса (для имён папок)."""
    if not code or code == LANG:
        return tr(text)
    table = _other.get(code)
    if table is None:
        table = _other[code] = _read(code) or {}
    return table.get(text) or EN.get(text) or text


def plural(n: int, one: str, few: str, many: str) -> str:
    """Форма слова по числу. Формы называются русскими словами; в языках без них берётся одна."""
    if _plural_rule == "slavic":
        tail = n % 100
        form = many if 11 <= tail <= 14 else {1: one, 2: few, 3: few, 4: few}.get(n % 10, many)
    elif _plural_rule == "polish":
        tail = n % 100
        form = one if n == 1 else few if n % 10 in (2, 3, 4) and not 12 <= tail <= 14 else many
    else:
        form = one if n == 1 else many
    return f"{n} {tr(form)}"


set_language("RU-ru")
