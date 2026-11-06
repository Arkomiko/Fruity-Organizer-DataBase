"""Горячие клавиши хранятся текстом, например "Ctrl+F".

Сравниваются по коду клавиши Windows, а не по символу, поэтому работают и в русской раскладке.
"""
from __future__ import annotations

# (действие, подпись, сочетание по умолчанию). Новое действие: строка здесь и метод _do_<действие> в App.
ACTIONS = (
    ("organize", "Организовать плагины", "Ctrl+Enter"),
    ("refresh", "Обновить список", "F5"),
    ("find", "Поиск", "Ctrl+F"),
    ("filters", "Фильтры", "Ctrl+L"),
    ("backup", "Бэкап", "Ctrl+B"),
    ("undo", "Отменить", "Ctrl+Z"),
    ("tab_plugins", "Плагины", "Ctrl+1"),
    ("tab_settings", "Настройки", "Ctrl+2"),
    ("tab_about", "О программе", "Ctrl+3"),
)
_NAMED = {13: "Enter", 32: "Space", 33: "PgUp", 34: "PgDn", 35: "End", 36: "Home", 37: "Left", 38: "Up", 39: "Right", 40: "Down",
          45: "Insert", 46: "Delete"}
_MODIFIER_KEYS = {16, 17, 18, 91, 92, 160, 161, 162, 163, 164, 165}
SHIFT, CTRL, ALT = 0x1, 0x4, 0x20000


def key_name(vk: int) -> str:
    """Название клавиши по её коду. Пусто, если клавиша не подходит."""
    if 65 <= vk <= 90 or 48 <= vk <= 57:
        return chr(vk)
    if 112 <= vk <= 123:
        return f"F{vk - 111}"
    return _NAMED.get(vk, "")


def shortcut(vk: int, state: int) -> str:
    """Текст нажатого сочетания. Пусто, если сочетанием оно быть не может.

    Простая буква или цифра не подходит: она нужна для ввода текста в поиске.
    """
    name = key_name(vk)
    if not name or vk in _MODIFIER_KEYS:
        return ""
    held = [label for bit, label in ((CTRL, "Ctrl"), (ALT, "Alt"), (SHIFT, "Shift")) if state & bit]
    if not state & (CTRL | ALT) and not 112 <= vk <= 123:
        return ""
    return "+".join((*held, name))


def bindings(saved: dict | None) -> dict[str, str]:
    """{сочетание: действие}: значения по умолчанию плюс сохранённые. Пустое значение значит «без сочетания»."""
    result = {}
    for action, _label, default in ACTIONS:
        text = (saved or {}).get(action, default)
        if text:
            result[text] = action
    return result


def assign(saved: dict, action: str, text: str) -> dict:
    """Назначает сочетание действию. Если оно было занято, другое действие остаётся без него."""
    current = {a: saved.get(a, default) for a, _label, default in ACTIONS}
    if text:
        for other, value in current.items():
            if value == text and other != action:
                current[other] = ""
    current[action] = text
    return current
