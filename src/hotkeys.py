"""Горячие клавиши хранятся текстом, например "Ctrl+F".

Сравниваются по коду клавиши Windows, а не по символу, поэтому работают в любой раскладке:
Ctrl+F и Ctrl+А это одна и та же клавиша.
"""
from __future__ import annotations

import ctypes

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
    ("tab_mods", "Моды", "Ctrl+4"),
    ("restore", "Восстановить", "Ctrl+Shift+B"),
    ("star", "Ставит или снимает звезду", "Ctrl+D"),
    ("open_folder", "Открыть папку плагина", "Ctrl+O"),
    ("clear_filters", "Сбросить все", "Ctrl+Shift+L"),
    ("zoom_in", "Увеличить масштаб", "Ctrl+="),
    ("zoom_out", "Уменьшить масштаб", "Ctrl+-"),
    ("zoom_reset", "Сбросить масштаб", "Ctrl+0"),
    ("maximize", "Развернуть окно", "F11"),
    ("help", "Показать обучение", "F1"),
    ("wiki", "Справка", "Shift+F1"),
)
_NAMED = {13: "Enter", 32: "Space", 33: "PgUp", 34: "PgDn", 35: "End", 36: "Home", 37: "Left", 38: "Up", 39: "Right", 40: "Down",
          45: "Insert", 46: "Delete", 186: ";", 187: "=", 188: ",", 189: "-", 190: ".", 191: "/", 192: "`", 219: "[", 220: "\\", 221: "]", 222: "'",
          **{96 + digit: f"Num{digit}" for digit in range(10)}}
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


def _layout_chars(vk: int) -> list[str]:
    """Что эта клавиша печатает в установленных раскладках Windows."""
    try:
        user32 = ctypes.windll.user32
        user32.ToUnicodeEx.argtypes = [ctypes.c_uint, ctypes.c_uint, ctypes.c_char_p, ctypes.c_wchar_p, ctypes.c_int, ctypes.c_uint, ctypes.c_void_p]
        count = user32.GetKeyboardLayoutList(0, None)
        layouts = (ctypes.c_void_p * count)()
        user32.GetKeyboardLayoutList(count, layouts)
        chars = []
        for layout in layouts:
            buffer = ctypes.create_unicode_buffer(8)
            # Флаг 4: не менять состояние клавиатуры, иначе сломается следующий набор текста.
            if user32.ToUnicodeEx(vk, user32.MapVirtualKeyW(vk, 0), bytes(256), buffer, 8, 4, layout) == 1:
                char = buffer.value.upper()
                if char.isprintable() and not char.isspace() and char not in chars:
                    chars.append(char)
        return chars
    except (AttributeError, OSError):
        return []


def display(text: str) -> str:
    """Сочетание для таблицы: рядом буквы той же клавиши в других раскладках, например Ctrl+F (А)."""
    name = text.rsplit("+", 1)[-1] or text[-1:]
    vk = next((code for code in (*range(48, 58), *range(65, 91), *_NAMED) if key_name(code) == name), None)
    printable = vk is not None and (65 <= vk <= 90 or 48 <= vk <= 57 or vk >= 186)
    others = [char for char in _layout_chars(vk) if char != name] if printable else []
    return f"{text} ({' '.join(others)})" if others else text


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
