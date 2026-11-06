"""Темы FL Studio: чтение активного .flstheme и расчёт цветов интерфейса.

Файл темы это список ключ=значение. Акцентные цвета записаны как Delphi TColor (0xBBGGRR, старший байт
не важен). Основной цвет задают четыре ручки от -256 до 256, они применяются к стандартной палитре.
Формула подобрана по миниатюрам тем из FL Studio: результат близок к оригиналу, но не совпадает до пикселя.
"""
from __future__ import annotations

import base64
import colorsys
import os
import re
import struct
import zlib

# Цвета при нейтральных ручках: так выглядит стандартное окно Plugin Manager.
BASE = {
    "EDGE": "#3C454A", "FRAME": "#5B6469", "PANEL": "#4D565C", "GROUP": "#3C454B", "GROUP_HEAD": "#363F45",
    "GROUP_LINE": "#2E363B", "BOX": "#333C42", "BOX_LINE": "#2A333A", "ROW_A": "#313A40", "ROW_B": "#353E44",
    "GRID_LINE": "#273036", "HEADER": "#252B2F", "THUMB": "#182127", "TAB_ON": "#262B2F", "TAB_OFF": "#353A3F",
    "BTN_TOP": "#343A3E", "BTN_BOTTOM": "#262C30", "BTN_BORDER": "#1F282E", "BTN_HOVER_TOP": "#3D4448",
    "BTN_HOVER_BOTTOM": "#2E3438", "TAB_BORDER": "#1A2329", "TAB_LINE": "#2A333A", "BTN_OFF_TOP": "#4A5359", "BTN_OFF_BOTTOM": "#434B51", "BTN_OFF_BORDER": "#3C454A",
    "WIN_HOVER": "#6C767C", "DOTS": "#2F373C", "FIND_LINE": "#2A333A",
}
DEFAULT_ACCENTS = {
    "SELECT": "#1565B8", "FOCUS": "#1367B8", "TEXT": "#BDC6CB", "TEXT_DIM": "#8B959B", "TEXT_OFF": "#6E777C",
    "TEXT_SOFT": "#A9B3B9", "TEXT_BRIGHT": "#DCE2E6", "TITLE_TEXT": "#C3CCD1", "ORANGE": "#FFB23E", "WHITE": "#EEF3F6", "LED": "#E85028", "STAR": "#FFB23E",
}
DEFAULT_PALETTE = {**BASE, **DEFAULT_ACCENTS}


def tcolor(value: str | int) -> str:
    """Переводит Delphi TColor в #RRGGBB."""
    v = int(value) & 0xFFFFFF
    return "#%02X%02X%02X" % (v & 255, v >> 8 & 255, v >> 16 & 255)


def rgb(color: str) -> tuple[int, int, int]:
    """Цвет #RRGGBB как три числа."""
    return int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16)


def mix(a: str, b: str, t: float) -> str:
    """Смешивает цвета: t=0 даёт a, t=1 даёт b."""
    va, vb = rgb(a), rgb(b)
    return "#%02X%02X%02X" % tuple(round(x + (y - x) * t) for x, y in zip(va, vb))


def luminance(color: str) -> float:
    """Относительная яркость цвета по WCAG."""
    def channel(c: int) -> float:
        """Линейная яркость одного канала."""
        c /= 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = rgb(color)
    return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)


def contrast(a: str, b: str) -> float:
    """Контрастность двух цветов по WCAG."""
    la, lb = sorted((luminance(a), luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def readable_on(background: str) -> str:
    """Белый или почти чёрный: что лучше читается на этом фоне."""
    return max(("#FFFFFF", "#101316"), key=lambda ink: contrast(ink, background))


# --------------------------------------------------------------------------------------------
# Поиск и чтение активной темы
# --------------------------------------------------------------------------------------------
def _registry_theme_name() -> str:
    """ThemeFilename из новейшей установленной версии FL Studio."""
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Image-Line") as root:
            names = []
            i = 0
            while True:
                try:
                    names.append(winreg.EnumKey(root, i))
                except OSError:
                    break
                i += 1
        versions = [n for n in names if re.fullmatch(r"FL Studio \d+", n)]
        for name in sorted(versions, key=lambda n: int(n.rsplit(" ", 1)[1]), reverse=True):
            try:
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, rf"Software\Image-Line\{name}\General\Theme") as key:
                    return winreg.QueryValueEx(key, "ThemeFilename")[0] or ""
            except OSError:
                continue
    except (OSError, ImportError):
        pass
    return ""


def find_active_theme(db: str, install: str = "") -> str | None:
    """Находит тему FL Studio. Рабочая копия хранится как __current.flstheme."""
    candidates = []
    if db:
        fl_data = os.path.dirname(os.path.dirname(os.path.normpath(db)))  # ...\FL Studio\Presets\Plugin database
        themes = os.path.join(fl_data, "Settings", "Themes")
        name = _registry_theme_name()
        if name:
            candidates.append(os.path.join(themes, name))
        candidates.append(os.path.join(themes, "__current.flstheme"))
    if install:
        candidates.append(os.path.join(install, "Artwork", "Themes", "__current.flstheme"))
    return next((path for path in candidates if os.path.isfile(path)), None)


def read_theme(path: str) -> dict[str, str] | None:
    """Читает файл темы. None, если это не тема."""
    try:
        with open(path, "rb") as f:
            text = f.read().decode("utf-8-sig", "replace")
    except OSError:
        return None
    values = {}
    for line in text.splitlines():
        key, sep, value = line.partition("=")
        if sep:
            values[key.strip()] = value.strip()
    return values if "Hue" in values or "Highlight" in values else None


def _number(values: dict, key: str, default: float = 0.0, limit: float = 256.0) -> float:
    """Число из темы в допустимых пределах."""
    try:
        return max(-limit, min(limit, float(values.get(key, default))))
    except ValueError:
        return default


def _color(values: dict, key: str, default: str) -> str:
    """Цвет из темы или значение по умолчанию."""
    try:
        return tcolor(int(values[key]))
    except (KeyError, ValueError):
        return default


def _shift(color: str, hue: float, saturation: float, lightness: float, contrast_knob: float, pivot: float) -> str:
    """Применяет ручки темы к одному цвету."""
    r, g, b = rgb(color)
    h, l, s = colorsys.rgb_to_hls(r / 255, g / 255, b / 255)
    h = (h + hue / 256) % 1.0
    s *= 1 + saturation / 256 * (1.5 if saturation > 0 else 1.0)
    # Сначала растягиваем вокруг тона панели: контраст сохранится и в очень светлой, и в тёмной теме.
    l = pivot + (l - pivot) * (1 + contrast_knob / 256)
    if lightness < 0:
        l *= 1 + lightness / 256 * 0.6
    else:
        amount = min(0.9, lightness / 256 * 1.7)
        l = l + (1 - l) * amount
    s, l = max(0.0, min(1.0, s)), max(0.0, min(1.0, l))
    return "#%02X%02X%02X" % tuple(round(c * 255) for c in colorsys.hls_to_rgb(h, l, s))


def build_palette(values: dict | None) -> dict[str, str]:
    """Переводит значения темы в полную палитру интерфейса."""
    if not values:
        return dict(DEFAULT_PALETTE)
    hue = _number(values, "Hue")
    saturation = _number(values, "Saturation")
    lightness = _number(values, "Lightness")
    contrast_knob = _number(values, "Contrast")
    r, g, b = rgb(BASE["PANEL"])
    pivot = colorsys.rgb_to_hls(r / 255, g / 255, b / 255)[1]
    palette = {key: _shift(color, hue, saturation, lightness, contrast_knob, pivot) for key, color in BASE.items()}
    _add_accents(palette, _color(values, "TextColor", DEFAULT_ACCENTS["TEXT"]), _color(values, "Highlight", DEFAULT_ACCENTS["ORANGE"]),
                 _color(values, "Selected", DEFAULT_ACCENTS["SELECT"]), _color(values, "Option", DEFAULT_ACCENTS["LED"]))
    return palette


def _add_accents(palette: dict, text: str, highlight: str, selected: str, led: str) -> None:
    """Добавляет к палитре цвета текста и акцентов, следя за читаемостью."""
    panel, row = palette["PANEL"], palette["ROW_A"]
    if contrast(text, panel) < 3.0:  # пара цветов может скрыть текст
        text = readable_on(panel)
    if contrast(highlight, palette["GROUP"]) < 1.8:
        highlight = mix(highlight, text, 0.5)
    select_row = mix(selected, row, 0.45)
    palette.update(
        TEXT=mix(text, panel, 0.10), TEXT_SOFT=mix(text, panel, 0.26), TEXT_BRIGHT=text, TITLE_TEXT=mix(text, panel, 0.12), TEXT_DIM=mix(text, panel, 0.42),
        TEXT_OFF=mix(text, panel, 0.62), ORANGE=highlight, STAR=highlight, LED=led,
        SELECT=select_row, FOCUS=mix(selected, panel, 0.25), WHITE=readable_on(select_row),
    )


# Цвета, которые можно выбрать в своей теме: ключ палитры и стандартное значение.
CUSTOM_KEYS = {"PANEL": BASE["PANEL"], "TEXT": "#DCE2E6", "ORANGE": DEFAULT_ACCENTS["ORANGE"], "SELECT": DEFAULT_ACCENTS["SELECT"], "LED": DEFAULT_ACCENTS["LED"]}


def custom_palette(colors: dict | None) -> dict[str, str]:
    """Полная палитра из нескольких выбранных цветов: базовые тона сдвигаются вслед за фоном."""
    chosen = {key: (colors or {}).get(key) or stock for key, stock in CUSTOM_KEYS.items()}
    def hls(color):
        """Цвет в формате оттенок, светлота, насыщенность."""
        r, g, b = rgb(color)
        return colorsys.rgb_to_hls(r / 255, g / 255, b / 255)
    h0, l0, s0 = hls(BASE["PANEL"])
    h1, l1, s1 = hls(chosen["PANEL"])
    palette = {}
    for key, color in BASE.items():
        h, l, s = hls(color)
        l = max(0.0, min(1.0, l + l1 - l0))
        s = max(0.0, min(1.0, s * (s1 / s0 if s0 else 1.0)))
        palette[key] = "#%02X%02X%02X" % tuple(round(c * 255) for c in colorsys.hls_to_rgb((h + h1 - h0) % 1.0, l, s))
    palette["PANEL"] = chosen["PANEL"]
    _add_accents(palette, chosen["TEXT"], chosen["ORANGE"], chosen["SELECT"], chosen["LED"])
    return palette


# --------------------------------------------------------------------------------------------
# Картинки создаются на лету: PNG единственный формат с настоящей прозрачностью в Tk 8.6
# --------------------------------------------------------------------------------------------
def rgba_png(width: int, height: int, pixels: bytes) -> str:
    """Кодирует пиксели RGBA в PNG (base64)."""
    def chunk(tag: bytes, data: bytes) -> bytes:
        """Один блок формата PNG."""
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data))
    stride = width * 4
    raw = b"".join(b"\0" + pixels[y * stride:(y + 1) * stride] for y in range(height))
    png = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
           + chunk(b"IDAT", zlib.compress(raw, 1)) + chunk(b"IEND", b""))
    return base64.b64encode(png).decode("ascii")


def tint_mask(side: int, mask: bytes, color: str) -> str:
    """Заливает сохранённую маску прозрачности одним цветом."""
    r, g, b = rgb(color)
    pixels = bytearray(side * side * 4)
    pixels[0::4] = bytes([r]) * (side * side)
    pixels[1::4] = bytes([g]) * (side * side)
    pixels[2::4] = bytes([b]) * (side * side)
    pixels[3::4] = mask
    return rgba_png(side, side, bytes(pixels))


# Яркость диска от основного тона (0) до блика (1) по строкам от центра индикатора:
# светлый серп сверху, самая тёмная полоса под ним, свечение растёт к низу.
_LED_ROWS = {-4: 1.0, -3: 0.01, -2: 0.0, -1: 0.12, 0: 0.26, 1: 0.43, 2: 0.59, 3: 0.76, 4: 0.62}
_LED_SIZE = 15.0


def _led_tone(y: float) -> float:
    """Яркость диска индикатора по строке."""
    low = max(-4.0, min(3.999, y))
    base = int(low // 1)
    t = low - base
    if base < -4 or base + 1 > 4:
        return _LED_ROWS[max(-4, min(4, base))]
    return _LED_ROWS[base] + (_LED_ROWS[base + 1] - _LED_ROWS[base]) * t


def _lerp3(a, b, t):
    """Смешивает два цвета, заданных тремя числами."""
    return tuple(a[i] + (b[i] - a[i]) * t for i in range(3))


def led_image(side: int, color: str, rim: str, lit: bool = True) -> str:
    """Рисует индикатор слоями: светлый ободок, тёмное кольцо, диск с бликом и свечением."""
    rim_rgb = rgb(rim)
    if lit:
        mid = rgb(mix(color, "#FFFFFF", 0.16))
        high = rgb(mix(color, "#FFFDE0", 0.92))
        ring = rgb(mix(color, "#000000", 0.35))
        dark = rgb(mix(color, "#000000", 0.72))
    else:
        mid, high = rgb(color), rgb(mix(color, "#FFFFFF", 0.22))
        ring, dark = rgb("#252A2C"), rgb("#17191A")
    pixels = bytearray(side * side * 4)
    unit = _LED_SIZE / side
    edge = _lerp3(mid, ring, 0.28)
    for py in range(side):
        for px in range(side):
            # Берём центр пикселя: мягкие края дают сами переходы цветов.
            x = (px + 0.5 - side / 2) * unit
            y = (py + 0.5 - side / 2) * unit
            d = (x * x + y * y) ** 0.5
            if d >= 7.95:
                continue
            alpha = 1.0
            if d > 7.0:
                tone = rim_rgb
                alpha = (7.95 - d) / 0.95
            elif d > 5.66:
                tone = _lerp3(dark, rim_rgb, min(1.0, (d - 5.66) / 1.05))
            elif d > 5.0:
                tone = _lerp3(ring, dark, (d - 5.0) / 0.66)
            elif d > 4.75:
                tone = ring
            else:
                value = _led_tone(y) + (abs(x) / 3.0) ** 2 * max(0.0, -y) * 0.14
                tone = _lerp3(mid, high, min(1.0, value))
                if d > 3.9:
                    tone = _lerp3(tone, edge, min(1.0, (d - 3.9) / 0.85))
            offset = (py * side + px) * 4
            pixels[offset] = round(tone[0])
            pixels[offset + 1] = round(tone[1])
            pixels[offset + 2] = round(tone[2])
            pixels[offset + 3] = round(255 * alpha)
    return rgba_png(side, side, bytes(pixels))


def button_image(width: int, height: int, top: str, bottom: str, border: str) -> str:
    """Лицо кнопки: контур 1px со смягчёнными углами, лёгкая фаска и вертикальный градиент."""
    edge = rgb(border)
    rows = []
    for y in range(height):
        t = y / max(1, height - 1)
        body = rgb(mix(top, bottom, t))
        side = rgb(mix(mix(top, bottom, t), "#FFFFFF", 0.05))
        if y == 0 or y == height - 1:
            row = bytes((*edge, 70)) + bytes((*edge, 225)) + bytes((*edge, 255)) * (width - 4) + bytes((*edge, 225)) + bytes((*edge, 70))
        elif y == 1 or y == height - 2:
            light = rgb(mix(mix(top, bottom, t), "#FFFFFF", 0.055 if y == 1 else 0.03))
            row = bytes((*edge, 225)) + bytes((*light, 255)) * (width - 2) + bytes((*edge, 225))
        else:
            row = bytes((*edge, 255)) + bytes((*side, 255)) + bytes((*body, 255)) * (width - 4) + bytes((*side, 255)) + bytes((*edge, 255))
        rows.append(row)
    return rgba_png(width, height, b"".join(rows))
