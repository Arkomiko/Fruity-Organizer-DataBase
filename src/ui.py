"""Главное окно FODB. Всё рисуется на холстах (Canvas), чтобы размеры оставались точными при любом масштабе.

Короткие имена, которые встречаются везде:
    t  объект Theme (масштаб, шрифты, картинки);
    p  функция t.p: переводит размер из макета в экранные пиксели, p(19) это 19 пикселей при 100 %;
    c  холст (Canvas), на котором идёт рисование.
Цвета (PANEL, TEXT и другие) это переменные модуля: их заменяет активная тема.
"""
from __future__ import annotations

import base64
import ctypes
import os
import dataclasses
import queue
import sys
import threading
import time
import tkinter as tk
import tkinter.font as tkfont
import zlib
from ctypes import wintypes
from functools import lru_cache
from tkinter import filedialog

import about
import assets_data
import core
import hotkeys
import i18n
import rules
import theme as fltheme
from i18n import plural, tr
from theme import mix as lerp

APP_TITLE = "Fruity Organizer DataBase"
VERSION = "1.1.0.0611"
PROJECT_REPO = "Arkomiko/Fruity-Organizer-DataBase"
PROJECT_URL = "https://github.com/" + PROJECT_REPO

# Цвета интерфейса: заменяются все сразу при смене темы.
globals().update(fltheme.DEFAULT_PALETTE)



def columns() -> tuple:
    """Колонки списка: ключ, заголовок, ширина."""
    return (
        ("fav", "F", 24), ("name", tr("Название"), 150), ("status", tr("Статус"), 52), ("format", tr("Формат"), 72),
        ("bits", tr("Бит"), 36), ("type", tr("Тип"), 60), ("purpose", tr("Назначение"), 118), ("vendor", tr("Вендор"), 130),
        ("file", tr("Файл"), 170), ("path", tr("Путь"), 80),
    )


SKIP_LABELS = {
    "organized": "уже организовано", "duplicate": "другие форматы того же плагина", "error": "с ошибками сканирования",
    "no_file": "без файла пресета", "in_place": "уже на своём месте",
}
# Меню фильтров: левая и правая колонки. Новый фильтр: строка здесь и поле в rules.FIELDS.
FILTER_GROUPS_LEFT = (
    ("kind", "Тип", {"Effects": "Эффекты", "Generators": "Генераторы"}),
    ("format", "Формат", {}),
    ("bits", "Разрядность", {}),
    ("status", "Статус", {"ok": "Рабочие", "error": "С ошибками"}),
    ("organized", "Организация", {"yes": "Организованные", "no": "Неорганизованные"}),
    ("formats_count", "Форматов у плагина", {"multi": "Несколько", "single": "Один"}),
    ("age", "Дата файла", {"7d": "За 7 дней", "30d": "За 30 дней", "90d": "За 90 дней", "365d": "За год"}),
    ("size", "Размер файла", {"small": "До 10 МБ", "medium": "10–100 МБ", "large": "Больше 100 МБ"}),
    ("source", "Как определено назначение", {"manual": "Вручную", "rule": "Ваше правило", "name": "Справочник имён",
                                             "category": "Категория плагина", "keyword": "Слова в имени", "fallback": "Не определено"}),
    ("edited", "Вендор", {"yes": "Изменён вручную", "no": "Как в плагине"}),
)
FILTER_GROUPS_MIDDLE = (("purpose", "Назначение", {}),)
FILTER_GROUPS_RIGHT = (("vendor", "Производитель", {}),)


def plugins_word(n: int) -> str:
    """Число со словом «плагин» в нужной форме."""
    return plural(n, tr("плагин"), tr("плагина"), tr("плагинов"))


# --------------------------------------------------------------------------------------------
# Функции Windows для окна
# --------------------------------------------------------------------------------------------
user32 = ctypes.windll.user32
user32.GetParent.restype = wintypes.HWND
user32.GetParent.argtypes = [wintypes.HWND]
user32.GetWindowLongPtrW.restype = ctypes.c_ssize_t
user32.GetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int]
user32.SetWindowLongPtrW.restype = ctypes.c_ssize_t
user32.SetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_ssize_t]
user32.SendMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
user32.MonitorFromWindow.restype = wintypes.HMONITOR
user32.MonitorFromWindow.argtypes = [wintypes.HWND, wintypes.DWORD]


class MONITORINFO(ctypes.Structure):
    """Структура Windows с границами монитора."""
    _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT), ("rcWork", wintypes.RECT),
                ("dwFlags", wintypes.DWORD)]


user32.GetMonitorInfoW.argtypes = [wintypes.HMONITOR, ctypes.POINTER(MONITORINFO)]
user32.CreateWindowExW.restype = wintypes.HWND
user32.CreateWindowExW.argtypes = [wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                   wintypes.HWND, wintypes.HMENU, wintypes.HINSTANCE, wintypes.LPVOID]
user32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.UINT]
user32.SetLayeredWindowAttributes.argtypes = [wintypes.HWND, wintypes.COLORREF, wintypes.BYTE, wintypes.DWORD]
user32.SetClassLongPtrW.restype = ctypes.c_ssize_t
user32.SetClassLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_ssize_t]
user32.InvalidateRect.argtypes = [wintypes.HWND, wintypes.LPVOID, wintypes.BOOL]
user32.UpdateWindow.argtypes = [wintypes.HWND]
ctypes.windll.gdi32.CreateSolidBrush.restype = wintypes.HBRUSH
ctypes.windll.gdi32.CreateSolidBrush.argtypes = [wintypes.COLORREF]
ctypes.windll.gdi32.DeleteObject.argtypes = [wintypes.HGDIOBJ]
ctypes.windll.kernel32.GetModuleHandleW.restype = wintypes.HMODULE
ctypes.windll.kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
ctypes.windll.kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]


class _WindowClass(ctypes.Structure):
    """Структура Windows WNDCLASS."""
    _fields_ = [("style", wintypes.UINT), ("proc", ctypes.c_void_p), ("extra", ctypes.c_int), ("window_extra", ctypes.c_int), ("instance", wintypes.HINSTANCE),
                ("icon", wintypes.HANDLE), ("cursor", wintypes.HANDLE), ("background", wintypes.HANDLE), ("menu", wintypes.LPCWSTR), ("name", wintypes.LPCWSTR)]


class Curtain:
    """Панель поверх части окна, которая плавно гаснет и смягчает смену страницы.

    Пропускает клики и не забирает фокус. Накрывает любые виджеты, чего не могут элементы холста.
    """

    def __init__(self):
        """Само окно создаётся при первом показе."""
        self.window = None
        self.brush = None

    def show(self, owner: int, x: int, y: int, w: int, h: int, color: str) -> None:
        """Показывает непрозрачную панель заданного цвета."""
        if self.window is None:
            instance = ctypes.windll.kernel32.GetModuleHandleW(None)
            proc = ctypes.cast(user32.DefWindowProcW, ctypes.c_void_p)
            user32.RegisterClassW(ctypes.byref(_WindowClass(proc=proc, instance=instance, name="FODBCurtain")))
            self.window = user32.CreateWindowExW(0x80000 | 0x20 | 0x8000000 | 0x80, "FODBCurtain", None, 0x80000000, x, y, w, h, owner, None, instance, None)
        r, g, b = fltheme.rgb(color)
        brush = ctypes.windll.gdi32.CreateSolidBrush(r | g << 8 | b << 16)
        user32.SetClassLongPtrW(self.window, -10, brush)
        if self.brush:
            ctypes.windll.gdi32.DeleteObject(self.brush)
        self.brush = brush
        self.alpha(1.0)
        user32.SetWindowPos(self.window, 0, x, y, w, h, 0x10 | 0x40)  # показать, не забирая фокус
        user32.InvalidateRect(self.window, None, True)
        user32.UpdateWindow(self.window)

    def alpha(self, value: float) -> None:
        """Задаёт непрозрачность от 0 до 1."""
        user32.SetLayeredWindowAttributes(self.window, 0, round(255 * value), 2)

    def hide(self) -> None:
        """Скрывает панель."""
        user32.ShowWindow(self.window, 0)


class Motion:
    """Один таймер на все плавные переходы. Работает, только пока что-то движется."""

    def __init__(self, root: tk.Misc, enabled: bool = True):
        """enabled: включены ли анимации."""
        self.root, self.enabled = root, enabled
        self.jobs: dict = {}
        self.running = False

    def run(self, key, ms: int, step, done=None) -> None:
        """Запускает переход: step(доля от 0 до 1) вызывается каждый кадр. Новый переход с тем же key заменяет старый."""
        if not self.enabled:
            step(1.0)
            if done:
                done()
            return
        self.jobs[key] = (time.perf_counter(), ms / 1000, step, done)
        if not self.running:
            self.running = True
            self.root.after(15, self._tick)

    def _tick(self) -> None:
        """Один кадр всех активных переходов."""
        now = time.perf_counter()
        for key, (start, length, step, done) in list(self.jobs.items()):
            share = min(1.0, (now - start) / length)
            try:
                step(share)
                if share >= 1.0:
                    if done:
                        done()
            except tk.TclError:  # виджет исчез во время перехода
                share = 1.0
            if share >= 1.0 and self.jobs.get(key, (start,))[0] == start:
                del self.jobs[key]
        if self.jobs:
            self.root.after(15, self._tick)
        else:
            self.running = False


def fade_in_window(window: tk.Misc, motion: Motion, ms: int = 130) -> None:
    """Плавно проявляет окно."""
    if motion.enabled:
        window.attributes("-alpha", 0.0)
        motion.run(id(window), ms, lambda share: window.attributes("-alpha", share))


def enable_dpi_awareness() -> float:
    """Просит у Windows точные пиксели и возвращает масштаб экрана."""
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except (OSError, AttributeError):
        try:
            user32.SetProcessDPIAware()
        except (OSError, AttributeError):
            pass
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Arkomiko.FODB")
    except (OSError, AttributeError):
        pass
    dc = user32.GetDC(None)
    dpi = ctypes.windll.gdi32.GetDeviceCaps(dc, 88)
    user32.ReleaseDC(None, dc)
    return max(1.0, dpi / 96)


def hwnd_of(window: tk.Misc) -> int:
    """Дескриптор окна Windows для окна Tk."""
    return user32.GetParent(window.winfo_id())


def make_app_window(window: tk.Misc) -> None:
    """Даёт окну без рамки кнопку на панели задач и обычное сворачивание."""
    hwnd = hwnd_of(window)
    ex = user32.GetWindowLongPtrW(hwnd, -20)
    user32.SetWindowLongPtrW(hwnd, -20, (ex & ~0x80) | 0x40000)  # обычное окно с кнопкой на панели задач
    style = user32.GetWindowLongPtrW(hwnd, -16)
    user32.SetWindowLongPtrW(hwnd, -16, style | 0x20000 | 0x80000)  # разрешить сворачивание


def begin_native_move(window: tk.Misc) -> None:
    """Передаёт перетаскивание окна системе Windows."""
    hwnd = hwnd_of(window)
    user32.ReleaseCapture()
    user32.SendMessageW(hwnd, 0xA1, 2, 0)  # как будто нажат заголовок окна


def work_area(window: tk.Misc) -> tuple[int, int, int, int]:
    """Рабочая область монитора без панели задач: x, y, ширина, высота."""
    info = MONITORINFO()
    info.cbSize = ctypes.sizeof(MONITORINFO)
    user32.GetMonitorInfoW(user32.MonitorFromWindow(hwnd_of(window), 2), ctypes.byref(info))
    r = info.rcWork
    return r.left, r.top, r.right - r.left, r.bottom - r.top


# --------------------------------------------------------------------------------------------
# Тема: масштаб, шрифты, картинки, подгонка текста
# --------------------------------------------------------------------------------------------
class Theme:
    """Масштаб, шрифты, картинки и подгонка текста для текущей палитры."""

    def __init__(self, root: tk.Misc, scale: float, family: str = "Segoe UI", size: int = 11, motion: Motion | None = None):
        """scale: множитель размеров; family и size: шрифт; motion: таймер переходов."""
        self.root = root
        self.scale = scale
        self.family, self.grow = family, size - 11
        self.motion = motion or Motion(root, False)
        self.font = self._font(11)
        self.font_bold = self._font(11, True)
        self.font_title = tkfont.Font(root=self.root, family="Segoe UI Semibold" if family == "Segoe UI" else family, size=-self.p(13 + self.grow),
                                      weight="normal" if family == "Segoe UI" else "bold")
        self.font_big = self._font(12)
        self.images = self._make_images()
        self._gradients: dict = {}
        self._fit = lru_cache(maxsize=16384)(self._fit_uncached)

    def _make_images(self) -> dict[str, tk.PhotoImage]:
        """Создаёт значки в цветах палитры."""
        bucket = min(assets_data.DATA, key=lambda s: abs(s - self.scale))
        colors = {"star_on": STAR, "star_off": lerp(ROW_B, TEXT, 0.28), "up": THUMB, "down": THUMB, "win_min": TEXT_BRIGHT, "win_max": TEXT_BRIGHT,
                  "win_close": TEXT_BRIGHT, "folder": TEXT_BRIGHT, "folder_plus": TEXT_BRIGHT, "folder_x": TEXT_BRIGHT, "filter": TEXT_BRIGHT}
        images = {}
        for name, (side, packed) in assets_data.DATA[bucket].items():
            mask = zlib.decompress(base64.b64decode(packed))
            images[name] = tk.PhotoImage(master=self.root, data=fltheme.tint_mask(side, mask, colors.get(name, TEXT)))
        images["filter_on"] = tk.PhotoImage(master=self.root, data=fltheme.tint_mask(*self._mask(bucket, "filter"), ORANGE))
        images["caret"] = tk.PhotoImage(master=self.root, data=fltheme.tint_mask(*self._mask(bucket, "down"), TEXT_DIM))
        side = self.p(15)
        rim = lerp(GROUP, "#FFFFFF", 0.28)
        images["led_on"] = tk.PhotoImage(master=self.root, data=fltheme.led_image(side, LED, rim))
        images["led_off"] = tk.PhotoImage(master=self.root, data=fltheme.led_image(side, lerp(GROUP, TEXT, 0.14), rim, lit=False))
        return images

    @staticmethod
    def _mask(bucket: float, name: str) -> tuple[int, bytes]:
        """Распаковывает маску значка."""
        side, packed = assets_data.DATA[bucket][name]
        return side, zlib.decompress(base64.b64decode(packed))

    def _font(self, size: int, bold: bool = False) -> tkfont.Font:
        """Шрифт заданного размера с учётом масштаба."""
        return tkfont.Font(root=self.root, family=self.family, size=-self.p(size + self.grow), weight="bold" if bold else "normal")

    def led_frames(self) -> list[tk.PhotoImage]:
        """Промежуточные кадры индикатора. Рисуются при первом переключении."""
        if not hasattr(self, "_led_frames"):
            side, rim = self.p(15), lerp(GROUP, "#FFFFFF", 0.28)
            dim = lerp(GROUP, TEXT, 0.14)
            middle = [tk.PhotoImage(master=self.root, data=fltheme.led_image(side, lerp(dim, LED, share), rim)) for share in (0.35, 0.7)]
            self._led_frames = [self.images["led_off"], *middle, self.images["led_on"]]
        return self._led_frames

    def p(self, value: float) -> int:
        """Переводит размер из макета в экранные пиксели."""
        return round(value * self.scale)

    def gradient(self, width: int, height: int, top: str, bottom: str, border: str = "#000000") -> tk.PhotoImage:
        """Лицо кнопки из кэша."""
        key = (width, height, top, bottom, border)
        image = self._gradients.get(key)
        if image is None:
            image = tk.PhotoImage(master=self.root, data=fltheme.button_image(width, height, top, bottom, border))
            self._gradients[key] = image
        return image

    def soft_frame(self, canvas: tk.Canvas, box, color: str, under: str, thick: int, tags) -> None:
        """Рамка со слегка срезанными углами."""
        x0, y0, x1, y1 = box
        cut = self.p(1)
        bars = ((x0 + cut, y0, x1 - cut, y0 + thick), (x0 + cut, y1 - thick, x1 - cut, y1),
                (x0, y0 + cut, x0 + thick, y1 - cut), (x1 - thick, y0 + cut, x1, y1 - cut))
        for bar in bars:
            canvas.create_rectangle(*bar, fill=color, outline="", tags=tags)
        soft = lerp(color, under, 0.55)
        for cx, cy in ((x0, y0), (x1 - cut, y0), (x0, y1 - cut), (x1 - cut, y1 - cut)):
            canvas.create_rectangle(cx, cy, cx + cut, cy + cut, fill=soft, outline="", tags=tags)

    def fit(self, text: str, width: int, middle: bool = False) -> str:
        """Обрезает текст по ширине с двумя точками."""
        return self._fit(text, width, middle)

    def _fit_uncached(self, text: str, width: int, middle: bool) -> str:
        """Подбирает самую длинную подходящую часть двоичным поиском. middle: убрать середину."""
        measure = self.font.measure
        if not text or measure(text) <= width:
            return text
        if width <= 0:
            return ""
        if middle:
            lo, hi = 0, len(text)
            while lo < hi:  # наибольшее число символов, которое ещё помещается
                mid = (lo + hi + 1) // 2
                left = (mid + 1) // 3
                candidate = text[:left] + ".." + text[len(text) - (mid - left):]
                if measure(candidate) <= width:
                    lo = mid
                else:
                    hi = mid - 1
            left = (lo + 1) // 3
            return text[:left] + ".." + text[len(text) - (lo - left):] if lo else ".."
        lo, hi = 0, len(text)
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if measure(text[:mid] + "..") <= width:
                lo = mid
            else:
                hi = mid - 1
        return text[:lo] + ".."


class Button:
    """Плоская кнопка с градиентом на холсте: картинка и подпись поверх неё."""

    def __init__(self, canvas: tk.Canvas, theme: Theme, x, y, w, h, text, command, tags=(), font=None):
        """Рисует кнопку и подключает мышь."""
        self.canvas, self.theme, self.command = canvas, theme, command
        self.w, self.h = w, h
        self.enabled = True
        self.glow = 0.0
        self.painted = None
        self.tag = f"btn{id(self)}"
        self.image = canvas.create_image(x, y, anchor="nw", tags=(self.tag, *tags))
        self.label = canvas.create_text(x + w // 2, y + h // 2, text=text, fill=TEXT, font=font or theme.font,
                                        state="disabled", tags=tags)
        self._paint(0.0)
        canvas.itemconfigure(self.label, fill=TEXT_SOFT)
        canvas.tag_bind(self.tag, "<Enter>", lambda e: self._hover(True))
        canvas.tag_bind(self.tag, "<Leave>", lambda e: self._hover(False))
        canvas.tag_bind(self.tag, "<ButtonRelease-1>", self._release)

    def _paint(self, glow: float) -> None:
        """Рисует кнопку; glow: степень подсветки от 0 до 1."""
        glow = round(glow * 4) / 4  # нескольких шагов хватает для плавности, а кэш картинок остаётся маленьким
        look = (glow, self.enabled)
        if look == self.painted:
            return
        self.painted = look
        if self.enabled:
            top, bottom = lerp(BTN_TOP, BTN_HOVER_TOP, glow), lerp(BTN_BOTTOM, BTN_HOVER_BOTTOM, glow)
        else:
            top, bottom = BTN_OFF_TOP, BTN_OFF_BOTTOM
        image = self.theme.gradient(self.w, self.h, top, bottom, BTN_BORDER if self.enabled else BTN_OFF_BORDER)
        self.canvas.itemconfigure(self.image, image=image)

    def _hover(self, hover: bool) -> None:
        """Плавно меняет подсветку при наведении."""
        start, target = self.glow, 1.0 if hover else 0.0

        def step(share):
            """Один шаг перехода."""
            self.glow = start + (target - start) * share
            self._paint(self.glow)
        self.theme.motion.run(self.tag, 110, step)

    def _release(self, _event) -> None:
        """Клик по кнопке."""
        if self.enabled:
            self.command()

    def set_enabled(self, enabled: bool) -> None:
        """Включает или выключает кнопку."""
        self.enabled = enabled
        self.canvas.itemconfigure(self.label, fill=TEXT_SOFT if enabled else TEXT_OFF)
        self.glow = 0.0
        self._paint(0.0)

    def set_text(self, text: str) -> None:
        """Меняет подпись."""
        self.canvas.itemconfigure(self.label, text=text)


# --------------------------------------------------------------------------------------------
# Таблица плагинов: на холсте существуют только видимые строки
# --------------------------------------------------------------------------------------------
class Grid:
    """Таблица плагинов. На холсте существуют только видимые строки, поэтому длинный список не тормозит."""

    def __init__(self, parent: tk.Misc, theme: Theme, widths: dict, sort: list, on_select, on_star, on_menu, order=None, hidden=None):
        """Запоминает данные и подключает события."""
        self.t = theme
        self.on_select, self.on_star, self.on_menu = on_select, on_star, on_menu
        self.on_double = lambda plugin: None
        self.on_header_menu = lambda event: None
        p = theme.p
        self.row_h = max(p(19), theme.font.metrics("linespace") + p(2))
        self.head_h = p(19)
        self.scroll_w = p(17)
        self.c = tk.Canvas(parent, bg=ROW_A, highlightthickness=0, takefocus=1, bd=0)
        table = columns()
        self.widths = {key: p(widths.get(key, width)) for key, _, width in table}
        known = [key for key, _, _ in table]
        self.hidden = set(hidden or ())
        saved = [key for key in (order or []) if key in known and key != "fav"]
        self.order = ["fav", *saved, *[key for key in known if key not in saved and key != "fav"]]
        self.labels = {key: label for key, label, _ in table}
        self.head_press = None
        self.head_drag = False
        self.on_layout = lambda: None
        self.on_focus = lambda: None
        self.sort_key, self.sort_reverse = sort
        self.items: list[core.Plugin] = []
        self.top = 0
        self.selected: set[str] = set()
        self.anchor = 0
        self.cursor = 0
        self.pool: list[dict] = []
        self.size = (0, 0)
        self.drag_col = None
        self.drag_thumb = None
        c = self.c
        c.bind("<FocusIn>", lambda e: self._draw_frame())
        c.bind("<FocusOut>", lambda e: self._draw_frame())
        c.bind("<Configure>", self._configure)
        c.bind("<MouseWheel>", lambda e: self.scroll(-3 if e.delta > 0 else 3))
        c.bind("<Button-1>", self._press)
        c.bind("<B1-Motion>", self._drag)
        c.bind("<ButtonRelease-1>", self._release)
        c.bind("<Motion>", self._motion)
        c.bind("<Button-3>", self._right)
        c.bind("<Double-Button-1>", self._double)
        c.bind("<Up>", lambda e: self._key_move(-1, e))
        c.bind("<Down>", lambda e: self._key_move(1, e))
        c.bind("<Prior>", lambda e: self._key_move(-self.visible_rows(), e))
        c.bind("<Next>", lambda e: self._key_move(self.visible_rows(), e))
        c.bind("<Home>", lambda e: self._key_move(-len(self.items), e))
        c.bind("<End>", lambda e: self._key_move(len(self.items), e))
        c.bind("<Control-KeyPress>", lambda e: self._select_all(e) if e.keycode == 65 else None)

    # разметка ----------------------------------------------------------------------------------
    def visible_rows(self) -> int:
        """Сколько строк помещается."""
        return max(1, (self.size[1] - self.head_h) // self.row_h)

    def _configure(self, event) -> None:
        """Размер изменился: перестраиваем."""
        size = (event.width, event.height)
        if size == self.size:
            return
        self.size = size
        self.rebuild()

    def _col_x(self) -> list[tuple[str, str, int, int]]:
        """Положение колонок: последняя занимает всю оставшуюся ширину."""
        x = 1
        right = self.size[0] - self.scroll_w - 1
        result = []
        shown = [key for key in self.order if key not in self.hidden]
        last = len(shown) - 1
        for i, key in enumerate(shown):
            w = self.widths[key] if i < last else max(self.widths[key], right - x)
            result.append((key, self.labels[key], x, w))
            x += w
        return result

    def rebuild(self) -> None:
        """Создаёт заголовок, строки и полосу прокрутки заново."""
        c, t = self.c, self.t
        c.delete("all")
        self.pool = []
        self.cols = self._col_x()
        W, H = self.size
        right = W - self.scroll_w - 1
        c.create_rectangle(1, 1, right, self.head_h, fill=HEADER, outline="", tags="head")
        for key, label, x, w in self.cols:
            pad = t.p(6) if key != "fav" else t.p(5)
            if x + pad < right:
                caption = label
                if key == self.sort_key and key != "fav":
                    caption = f"{label} {'▼' if self.sort_reverse else '▲'}"
                c.create_text(x + pad, 1 + self.head_h // 2, text=t.fit(caption, min(w, right - x) - pad), anchor="w",
                              fill=TEXT_DIM, font=t.font, tags="head")
        rows = (H - self.head_h) // self.row_h + 2
        for r in range(rows):
            y = 1 + self.head_h + r * self.row_h
            row = {"bg": c.create_rectangle(1, y, right, y + self.row_h, fill=ROW_A, outline=""), "cells": {}, "values": {},
                   "plugin": None, "fill": None}
            for key, _, x, w in self.cols:
                if key == "fav":
                    row["star"] = c.create_image(x + w // 2 + t.p(1), y + self.row_h // 2, image=t.images["star_off"], state="hidden")
                elif x + t.p(6) < right:
                    row["cells"][key] = c.create_text(x + t.p(6), y + self.row_h // 2, text="", anchor="w", fill=TEXT,
                                                      font=t.font)
            self.pool.append(row)
        # Строки не должны рисоваться поверх заголовка и полосы прокрутки.
        c.tag_raise("head")
        self._build_scrollbar()
        self._draw_frame()
        self.top = min(self.top, max(0, len(self.items) - self.visible_rows()))
        self.draw()

    def _draw_frame(self) -> None:
        """Рамка: синяя при фокусе."""
        c, t = self.c, self.t
        c.delete("gframe")
        W, H = self.size
        if W <= 0:
            return
        if c.focus_displayof() is c:
            t.soft_frame(c, (0, 0, W, H), FOCUS, PANEL, t.p(2), "gframe")
        else:
            t.soft_frame(c, (0, 0, W, H), GRID_LINE, GRID_LINE, 1, "gframe")

    def _build_scrollbar(self) -> None:
        """Полоса прокрутки."""
        c, t = self.c, self.t
        W, H = self.size
        x0 = W - self.scroll_w - 1
        c.create_rectangle(x0, 1, W, H, fill=ROW_B, outline="", tags="sb")
        c.create_image(x0 + self.scroll_w // 2, 1 + t.p(9), image=t.images["up"], tags=("sb", "sb_up"))
        c.create_image(x0 + self.scroll_w // 2, H - t.p(9), image=t.images["down"], tags=("sb", "sb_down"))
        cx = x0 + self.scroll_w // 2
        half = max(1, t.p(1.5))
        self.thumb = c.create_rectangle(cx - half, 0, cx + half, 0, fill=THUMB, outline="", tags="sb")
        c.tag_bind("sb_up", "<Button-1>", lambda e: self.scroll(-1))
        c.tag_bind("sb_down", "<Button-1>", lambda e: self.scroll(1))

    # данные -----------------------------------------------------------------------------------
    def set_items(self, items: list[core.Plugin]) -> None:
        """Новый список плагинов."""
        self.items = items
        self.top = min(self.top, max(0, len(items) - self.visible_rows()))
        self.cursor = min(self.cursor, max(0, len(items) - 1))
        self.draw()

    def selection(self) -> list[core.Plugin]:
        """Выбранные плагины."""
        return [p for p in self.items if p.key in self.selected]

    def _cell(self, p: core.Plugin, key: str) -> str:
        """Текст ячейки."""
        if key == "name":
            return p.name
        if key == "status":
            return "ok" if p.ok else tr("ошибка")
        if key == "format":
            return p.formats
        if key == "bits":
            return p.bits
        if key == "type":
            if not p.type_known and not p.ok:
                return "?"
            return tr("Эффект") if p.kind == "Effects" else tr("Синт")
        if key == "vendor":
            return p.vendor
        if key == "purpose":
            return rules.purpose_label(p.purposes[0]) if p.purposes else ""
        if key == "file":
            return p.filename
        return p.directory

    def draw(self) -> None:
        """Обновляет только изменившийся текст и цвет в строках."""
        if not self.pool:
            return
        c, t = self.c, self.t
        widths = {key: w for key, _, _, w in self.cols}
        right = self.size[0] - self.scroll_w - 1
        positions = {key: x for key, _, x, _ in self.cols}
        pad = t.p(6)
        count = len(self.items)
        for r, row in enumerate(self.pool):
            index = self.top + r
            plugin = self.items[index] if index < count else None
            selected = plugin is not None and plugin.key in self.selected
            fill = SELECT if selected else (ROW_B if index % 2 else ROW_A)
            if row["fill"] != fill:
                c.itemconfigure(row["bg"], fill=fill)
                row["fill"] = fill
            star = None if plugin is None else ("star_on" if plugin.organized_in else "star_off")
            if row.get("star_value") != star:
                if star:
                    c.itemconfigure(row["star"], image=t.images[star], state="normal")
                else:
                    c.itemconfigure(row["star"], state="hidden")
                row["star_value"] = star
            ink = WHITE if selected else TEXT
            if row.get("ink") != ink:
                for key, item in row["cells"].items():
                    c.itemconfigure(item, fill=(TEXT_BRIGHT if key == "name" and not selected else ink))
                row["ink"] = ink
            for key, item in row["cells"].items():
                value = ""
                if plugin is not None:
                    width = min(widths[key], right - positions[key]) - pad - t.p(2)
                    value = t.fit(self._cell(plugin, key), width, middle=key in ("path", "file"))
                if row["values"].get(key) != value:
                    c.itemconfigure(item, text=value)
                    row["values"][key] = value
        self._draw_thumb()

    def _thumb_range(self) -> tuple[int, int, int, int]:
        """Положение ползунка: верх, низ, начало дорожки и свободный ход."""
        t = self.t
        H = self.size[1]
        track0, track1 = t.p(18), H - t.p(18)
        span = max(1, track1 - track0)
        visible = self.visible_rows()
        total = max(1, len(self.items))
        length = max(t.p(16), span * min(1.0, visible / total))
        room = span - length
        maxtop = max(1, total - visible)
        y0 = track0 + room * (self.top / maxtop if total > visible else 0)
        return round(y0), round(y0 + length), track0, round(room)

    def _draw_thumb(self) -> None:
        """Двигает ползунок."""
        y0, y1, _, _ = self._thumb_range()
        x0, _, x1, _ = self.c.coords(self.thumb)
        self.c.coords(self.thumb, x0, y0, x1, y1)
        hidden = len(self.items) <= self.visible_rows()
        self.c.itemconfigure(self.thumb, state="hidden" if hidden else "normal")

    def scroll(self, delta: int) -> None:
        """Прокручивает на delta строк."""
        top = max(0, min(self.top + delta, max(0, len(self.items) - self.visible_rows())))
        if top != self.top:
            self.top = top
            self.draw()

    def ensure_visible(self, index: int) -> None:
        """Прокручивает так, чтобы строка стала видна."""
        if index < self.top:
            self.top = index
        elif index >= self.top + self.visible_rows():
            self.top = index - self.visible_rows() + 1

    # ввод -------------------------------------------------------------------------------------
    def _row_at(self, y: int) -> int | None:
        """Номер строки по координате y (или None)."""
        if y <= self.head_h:
            return None
        index = self.top + (y - 1 - self.head_h) // self.row_h
        return index if 0 <= index < len(self.items) else None

    def _col_edge(self, x: int) -> str | None:
        """Колонка, чей правый край под мышью (для изменения ширины)."""
        slack = self.t.p(4)
        for key, _, cx, w in self.cols[:-1]:
            if abs(x - (cx + w)) <= slack:
                return key
        return None

    def _in_scrollbar(self, x: int) -> bool:
        """Находится ли мышь над полосой прокрутки."""
        return x >= self.size[0] - self.scroll_w - 1

    def _motion(self, event) -> None:
        """Курсор изменения ширины на границе колонок."""
        head = event.y <= self.head_h and not self._in_scrollbar(event.x)
        self.c.configure(cursor="sb_h_double_arrow" if head and self._col_edge(event.x) else "")

    def _press(self, event) -> None:
        """Нажатие: ползунок, заголовок, звезда или строка."""
        self.c.focus_set()
        self.on_focus()
        self.drag_col = None
        self.drag_thumb = None
        if self._in_scrollbar(event.x):
            y0, y1, track0, room = self._thumb_range()
            if y0 <= event.y <= y1:
                self.drag_thumb = (event.y, self.top)
            elif track0 < event.y < self.size[1] - track0:
                self.scroll(-self.visible_rows() if event.y < y0 else self.visible_rows())
            return
        if event.y <= self.head_h:
            edge = self._col_edge(event.x)
            if edge:
                self.drag_col = (edge, event.x, self.widths[edge])
            else:
                for key, _, x, w in self.cols:
                    if x <= event.x < x + w:
                        self.head_press = (key, event.x)
                        self.head_drag = False
                        break
            return
        index = self._row_at(event.y)
        if index is None:
            return
        if event.x < self.cols[0][3] + 1 and not event.state & 0x5:
            self.on_star(self.items[index])
            return
        self._select_click(index, event.state)

    def _select_click(self, index: int, state: int) -> None:
        """Выделение строки с учётом Shift и Ctrl."""
        shift, ctrl = state & 0x1, state & 0x4
        key = self.items[index].key
        if shift:
            a, b = sorted((self.anchor, index))
            if not ctrl:
                self.selected.clear()
            self.selected.update(p.key for p in self.items[a:b + 1])
        elif ctrl:
            self.selected.symmetric_difference_update({key})
            self.anchor = index
        else:
            self.selected = {key}
            self.anchor = index
        self.cursor = index
        self.draw()
        self.on_select()

    def _drag(self, event) -> None:
        """Движение с нажатой кнопкой: ползунок, ширина или порядок колонок."""
        if self.drag_thumb:
            start_y, start_top = self.drag_thumb
            _, _, _, room = self._thumb_range()
            maxtop = max(0, len(self.items) - self.visible_rows())
            if room > 0:
                top = start_top + round((event.y - start_y) * maxtop / room)
                self.scroll(top - self.top)
        elif self.drag_col:
            key, x0, w0 = self.drag_col
            self.widths[key] = max(self.t.p(24), w0 + event.x - x0)
            self.rebuild()
        elif self.head_press and self.head_press[0] != "fav":
            if abs(event.x - self.head_press[1]) > self.t.p(5):
                self.head_drag = True
            if self.head_drag:
                self._show_drop_marker(event.x)

    def _drop_index(self, x: int) -> int:
        """Куда встанет перетаскиваемая колонка. Колонка звезды всегда первая."""
        for index, (_key, _label, cx, w) in enumerate(self.cols):
            if x < cx + w / 2:
                return max(1, index)
        return len(self.cols)

    def _show_drop_marker(self, x: int) -> None:
        """Метка места вставки колонки."""
        index = self._drop_index(x)
        pos = self.cols[index][2] if index < len(self.cols) else self.size[0] - self.scroll_w - 1
        self.c.delete("drop")
        self.c.create_rectangle(pos - 1, 1, pos + 1, self.size[1], fill=ORANGE, outline="", tags="drop")
        self.c.configure(cursor="sb_h_double_arrow")

    def _release(self, event) -> None:
        """Отпускание: завершает перетаскивание или сортирует."""
        pressed, dragged = self.head_press, self.head_drag
        self.head_press, self.head_drag = None, False
        if self.drag_col:
            self.on_layout()
        self.drag_col = None
        self.drag_thumb = None
        if not pressed:
            return
        key = pressed[0]
        if dragged:
            self.c.delete("drop")
            self.c.configure(cursor="")
            index = self._drop_index(event.x)
            target = self.cols[index][0] if index < len(self.cols) else None
            if target != key:
                self.order.remove(key)
                self.order.insert(self.order.index(target) if target else len(self.order), key)
            self.rebuild()
            self.on_layout()
        elif key != "fav":
            self._sort_click(key)

    def _double(self, event) -> None:
        """Двойной клик по строке."""
        index = self._row_at(event.y)
        if index is not None and not self._in_scrollbar(event.x) and event.x >= self.cols[0][3] + 1:
            self.on_double(self.items[index])

    def show_row(self, key: str) -> None:
        """Прокручивает к плагину по ключу."""
        index = next((i for i, plugin in enumerate(self.items) if plugin.key == key), None)
        if index is not None:
            self.cursor = self.anchor = index
            self.ensure_visible(index)
            self.draw()

    def _right(self, event) -> None:
        """Правый клик: меню заголовка или строки."""
        self.c.focus_set()
        if event.y <= self.head_h and not self._in_scrollbar(event.x):
            self.on_header_menu(event)
            return
        index = self._row_at(event.y)
        if index is None:
            return
        if self.items[index].key not in self.selected:
            self._select_click(index, 0)
        self.on_menu(event)

    def _key_move(self, delta: int, event) -> str:
        """Движение по списку клавишами."""
        if not self.items:
            return "break"
        index = max(0, min(len(self.items) - 1, self.cursor + delta))
        if event.state & 0x1:
            a, b = sorted((self.anchor, index))
            self.selected = {p.key for p in self.items[a:b + 1]}
        else:
            self.selected = {self.items[index].key}
            self.anchor = index
        self.cursor = index
        self.ensure_visible(index)
        self.draw()
        self.on_select()
        return "break"

    def _select_all(self, _event) -> str:
        """Выделяет всё (Ctrl+A)."""
        self.selected = {p.key for p in self.items}
        self.draw()
        self.on_select()
        return "break"

    def _sort_click(self, key: str) -> None:
        """Клик по заголовку меняет сортировку."""
        if self.sort_key == key:
            self.sort_reverse = not self.sort_reverse
        else:
            self.sort_key, self.sort_reverse = key, False
        self.apply_sort()
        self.rebuild()

    def apply_sort(self) -> None:
        """Сортирует список."""
        key = self.sort_key
        cell = self._cell
        if key == "fav":
            self.items.sort(key=lambda p: (not p.organized_in, p.name.casefold()), reverse=self.sort_reverse)
        else:
            self.items.sort(key=lambda p: (cell(p, key).casefold(), p.name.casefold(), p.key), reverse=self.sort_reverse)


# --------------------------------------------------------------------------------------------
# Модальное окно в том же стиле
# --------------------------------------------------------------------------------------------
class Dialog:
    """Модальное окно в стиле программы: текст, поля, список и кнопки. Результат в result."""

    def __init__(self, master: tk.Misc, theme: Theme, title: str, message: str, buttons: list[str],
                 rows: list[tuple[str, str]] | None = None, width: int = 460, entry: str | None = None, fields=None,
                 choices: list[str] | None = None, current: str = "", text_view: str | None = None, on_key=None):
        """fields: (подпись, значение, варианты списка или None, подсказки или None) на строку."""
        self.result = None
        self.text = entry or ""
        self.values: list[str] = []
        self.choice = current
        t = self.t = theme
        p = t.p
        top = self.top = tk.Toplevel(master, bg=EDGE)
        top.withdraw()
        top.overrideredirect(True)
        top.attributes("-topmost", bool(master.attributes("-topmost")))
        W = p(width)
        inner = tk.Frame(top, bg=FRAME)
        inner.pack(fill="both", expand=True, padx=1, pady=1)
        head = tk.Canvas(inner, bg=FRAME, height=p(28), highlightthickness=0, width=W)
        head.pack(fill="x")
        head.create_text(p(10), p(14), text=title, anchor="w", fill=TITLE_TEXT, font=t.font_title)
        head.bind("<Button-1>", lambda e: begin_native_move(top))
        body = tk.Canvas(inner, bg=PANEL, highlightthickness=0, width=W)
        body.pack(fill="both", expand=True, padx=p(5), pady=(0, p(5)))
        y = p(14)
        if message:
            text_id = body.create_text(p(14), y, text=message, anchor="nw", fill=TEXT, font=t.font, width=W - p(40), justify="left")
            y = body.bbox(text_id)[3] + p(12)
        inner_w = W - p(10)
        self.field_vars = []
        for label, value, options, suggestions in fields or ():
            y = self._field(body, y, inner_w, label, value, options, suggestions)
        if choices is not None:
            y = self._choices(body, y, inner_w, choices, current)
        if text_view is not None:
            frame = tk.Frame(body, bg=GRID_LINE)
            box = tk.Text(frame, bg=ROW_A, fg=TEXT, font=t.font, bd=0, highlightthickness=0, wrap="none", height=24, padx=p(8), pady=p(4))
            box.pack(fill="both", expand=True, padx=1, pady=1)
            box.insert("end", text_view)
            box.see("end")
            box.configure(state="disabled")
            list_h = p(420)
            body.create_window(p(14), y, anchor="nw", window=frame, width=inner_w - p(28), height=list_h)
            y += list_h + p(12)
        if rows:
            shown = min(len(rows), 12)
            list_h = shown * (t.font.metrics("linespace") + p(3)) + p(6)
            frame = tk.Frame(body, bg=GRID_LINE)
            box = tk.Text(frame, bg=ROW_A, fg=TEXT, font=t.font, bd=0, highlightthickness=0, wrap="none", height=shown,
                          cursor="arrow", spacing1=p(2), spacing3=p(1), padx=p(8), tabs=(inner_w - p(70), "right"))
            box.pack(fill="both", expand=True, padx=1, pady=1)
            for label, value in rows:
                box.insert("end", f"{label}\t{value}\n")
            box.configure(state="disabled")
            body.create_window(p(14), y, anchor="nw", window=frame, width=inner_w - p(28), height=list_h)
            y += list_h + p(12)
        self.entry_var = None
        if entry is not None:
            self.entry_var = tk.StringVar(value=entry)
            field = tk.Entry(body, textvariable=self.entry_var, bg=BOX, fg=TEXT, insertbackground=TEXT, relief="flat", font=t.font_big,
                             highlightthickness=1, highlightbackground=BOX_LINE, highlightcolor=FOCUS, selectbackground=SELECT, selectforeground=WHITE)
            body.create_window(p(14), y, anchor="nw", window=field, width=inner_w - p(28), height=p(26))
            y += p(38)
            top.after(30, field.focus_set)
        bw, bh, gap = p(120), p(27), p(8)
        x = inner_w - p(14) - bw
        for index, label in reversed(list(enumerate(buttons))):
            Button(body, t, x, y, bw, bh, label, lambda v=index: self._close(v))
            x -= bw + gap
        body.configure(height=y + bh + p(14))
        if on_key:
            top.bind("<KeyPress>", lambda e: on_key(e, self))
        else:
            top.bind("<Escape>", lambda e: self._close(len(buttons) - 1 if len(buttons) > 1 else 0))
            top.bind("<Return>", lambda e: self._close(0))
        top.update_idletasks()
        w, h = top.winfo_reqwidth(), top.winfo_reqheight()
        mx, my, mw, mh = master.winfo_rootx(), master.winfo_rooty(), master.winfo_width(), master.winfo_height()
        top.geometry(f"{w}x{h}+{mx + (mw - w) // 2}+{my + (mh - h) // 2}")
        fade_in_window(top, t.motion)
        top.deiconify()
        top.lift()
        top.focus_force()
        top.grab_set()
        master.wait_window(top)

    def _field(self, body, y, inner_w, label, value, options, suggestions) -> int:
        """Одна строка формы. Возвращает следующую координату y."""
        t = self.t
        p = t.p
        x = p(150)
        field_w = inner_w - x - p(14)
        body.create_text(p(14), y + p(13), text=label, anchor="w", fill=TEXT_SOFT, font=t.font)
        var = tk.StringVar(value=value)
        self.field_vars.append(var)
        if options is None:
            field = tk.Entry(body, textvariable=var, bg=BOX, fg=TEXT, insertbackground=TEXT, relief="flat", font=t.font_big, highlightthickness=1,
                             highlightbackground=BOX_LINE, highlightcolor=FOCUS, selectbackground=SELECT, selectforeground=WHITE)
            room = field_w - (p(30) if suggestions else 0)
            body.create_window(x, y, anchor="nw", window=field, width=room, height=p(26))
            if len(self.field_vars) == 1:
                self.top.after(30, field.focus_set)
            if suggestions:
                self._drop(body, x + room + p(4), y, p(26), [(v, v) for v in suggestions], var)
        else:
            caption = next((text for v, text in options if v == value), value)
            self._drop(body, x, y, field_w, options, var, caption)
        return y + p(32)

    def _drop(self, body, x, y, w, options, var, caption=None) -> None:
        """Кнопка с меню вариантов, записывает выбор в var."""
        t = self.t
        button = None

        def popup():
            """Открывает меню вариантов."""
            menu = tk.Menu(self.top, tearoff=0, bg=GROUP, fg=TEXT, activebackground=SELECT, activeforeground=WHITE, bd=0, font=t.font, relief="flat")
            for value, label in options:
                def pick(v=value, l=label):
                    var.set(v)
                    if caption is not None:
                        button.set_text(l)
                menu.add_command(label=label, command=pick)
            menu.tk_popup(body.winfo_rootx() + x, body.winfo_rooty() + y + t.p(26))
        button = Button(body, t, x, y, w, t.p(26), caption or "", popup)
        body.create_image(x + w - t.p(12), y + t.p(13), image=t.images["caret"], state="disabled")

    def _choices(self, body, y, inner_w, choices, current) -> int:
        """Список с полем поиска. Возвращает следующую координату y."""
        t = self.t
        p = t.p
        query = tk.StringVar()
        entry = tk.Entry(body, textvariable=query, bg=BOX, fg=TEXT, insertbackground=TEXT, relief="flat", font=t.font_big, highlightthickness=1,
                         highlightbackground=BOX_LINE, highlightcolor=FOCUS, selectbackground=SELECT, selectforeground=WHITE)
        body.create_window(p(14), y, anchor="nw", window=entry, width=inner_w - p(28), height=p(26))
        y += p(32)
        listing = tk.Listbox(body, bg=ROW_A, fg=TEXT, font=t.font, bd=0, highlightthickness=1, highlightbackground=GRID_LINE, highlightcolor=GRID_LINE,
                             selectbackground=SELECT, selectforeground=WHITE, activestyle="none", exportselection=False)
        height = p(300)
        body.create_window(p(14), y, anchor="nw", window=listing, width=inner_w - p(28), height=height)

        def fill(*_args):
            """Заполняет список по тексту поиска."""
            word = query.get().casefold()
            listing.delete(0, "end")
            shown = [name for name in choices if word in name.casefold()]
            listing.insert("end", *shown)
            if self.choice in shown:
                listing.selection_set(shown.index(self.choice))
                listing.see(shown.index(self.choice))

        def chosen(_event):
            """Запоминает выбранный вариант."""
            picked = listing.curselection()
            if picked:
                self.choice = listing.get(picked[0])
        query.trace_add("write", fill)
        listing.bind("<<ListboxSelect>>", chosen)
        listing.bind("<Double-Button-1>", lambda e: self._close(0))
        fill()
        self.top.after(30, entry.focus_set)
        return y + height + p(12)

    def _close(self, value: int) -> None:
        """Закрывает окно. value: номер нажатой кнопки."""
        self.result = value
        if self.entry_var is not None:
            self.text = self.entry_var.get()
        self.values = [var.get() for var in self.field_vars]
        self.top.grab_release()
        self.top.destroy()


# --------------------------------------------------------------------------------------------
# Меню фильтров
# --------------------------------------------------------------------------------------------
class FilterPanel:
    """Выпадающее меню фильтров со счётчиками: в группе подходит любое значение, между группами все сразу."""

    def __init__(self, app, right: int, bottom: int):
        """Создаёт окно меню над кнопкой фильтра."""
        self.app = app
        t = self.t = app.t
        p = t.p
        top = self.top = tk.Toplevel(app.root, bg=BTN_BORDER)
        top.withdraw()
        top.overrideredirect(True)
        top.attributes("-topmost", True)
        self.width, self.height = p(760), min(p(560), app.root.winfo_height() - p(100))
        self.head_h = p(38)
        self.c = tk.Canvas(top, bg=GROUP, width=self.width, height=self.height, highlightthickness=0)
        self.c.pack(padx=1, pady=1)
        self.scroll = 0
        self.content_h = 0
        x, y = max(app.root.winfo_rootx(), right - self.width - 2), max(app.root.winfo_rooty(), bottom - self.height - 2)
        top.geometry(f"{self.width + 2}x{self.height + 2}+{x}+{y}")
        top.bind("<Escape>", lambda e: self.close())
        top.bind("<FocusOut>", lambda e: top.after(1, self._focus_check))
        self.c.bind("<MouseWheel>", self._wheel)
        self.redraw()
        fade_in_window(top, t.motion)
        top.deiconify()
        top.focus_force()

    def _focus_check(self) -> None:
        """Закрывает меню, если фокус ушёл."""
        try:
            if self.top.focus_displayof() is None:
                self.close()
        except (tk.TclError, KeyError):
            self.close()

    def close(self) -> None:
        """Закрывает меню."""
        self.app.filter_panel = None
        if self.top.winfo_exists():
            self.top.destroy()

    def _wheel(self, event) -> None:
        """Прокрутка колесом."""
        room = max(0, self.content_h - (self.height - self.head_h))
        self.scroll = max(0, min(room, self.scroll + (-self.t.p(40) if event.delta > 0 else self.t.p(40))))
        self.redraw()

    def redraw(self) -> None:
        """Рисует все группы заново."""
        c, t, app = self.c, self.t, self.app
        p = t.p
        c.delete("all")
        columns = ((FILTER_GROUPS_LEFT, p(10), p(230)), (FILTER_GROUPS_MIDDLE, p(248), p(240)), (FILTER_GROUPS_RIGHT, p(496), p(250)))
        query = app.query
        pool = app.source_plugins()
        bottom = 0
        for groups, x, width in columns:
            y = self.head_h + p(6) - self.scroll
            for name, title, labels in groups:
                y = self._group(name, title, labels, x, y, width, pool, query)
            bottom = max(bottom, y + self.scroll)
        self.content_h = bottom - self.head_h + p(8)
        c.create_rectangle(0, 0, self.width, self.head_h, fill=FRAME, outline="")
        active = sum(len(v) for v in app.s["filters"].values())
        title = tr("Фильтры") + (f" ({active})" if active else "")
        c.create_text(p(10), self.head_h // 2, text=title, anchor="w", fill=TITLE_TEXT, font=t.font_title)
        c.create_text(p(120), self.head_h // 2, text=tr("В поле поиска тоже можно: purpose:reverb,delay vendor:arturia -format:vst"),
                      anchor="w", fill=TEXT_DIM, font=t.font)
        Button(c, t, self.width - p(112), p(6), p(102), p(26), tr("Сбросить все"), self._reset)
        room = self.height - self.head_h
        if self.content_h > room:
            bar = room * room / self.content_h
            top = self.head_h + self.scroll * room / self.content_h
            c.create_rectangle(self.width - p(6), top, self.width - p(2), top + bar, fill=THUMB, outline="")

    def _group(self, name, title, labels, x, y, width, pool, query) -> int:
        """Рисует одну группу. Возвращает следующую координату y."""
        c, t, app = self.c, self.t, self.app
        p = t.p
        counts = rules.facet_counts(pool, name, query, app.s["filters"])
        chosen = set(app.s["filters"].get(name, ()))
        values = list(labels) if labels else sorted(counts, key=self._sort_key(name))
        for value in chosen:
            if value not in values:
                values.append(value)
        if not any(counts.get(v) or v in chosen for v in values):
            return y
        c.create_text(x, y + p(9), text=tr(title), anchor="w", fill=ORANGE if chosen else TEXT_DIM, font=t.font_bold)
        y += p(20)
        for value in values:
            count = counts.get(value, 0)
            if not count and value not in chosen:
                continue
            tag = f"row{id(value)}{name}"
            c.create_rectangle(x - p(4), y, x + width, y + p(19), fill=GROUP, outline="", tags=tag)
            box = (x, y + p(3), x + p(13), y + p(16))
            c.create_rectangle(*box, fill=BOX, outline=BOX_LINE, tags=tag)
            if value in chosen:
                c.create_image(x + p(6), y + p(10), image=t.images["check"], tags=tag)
            label = tr(labels[value]) if value in labels else self._value_label(name, value)
            room = width - p(58)
            c.create_text(x + p(19), y + p(9), text=t.fit(label or "—", room), anchor="w", fill=ORANGE if value in chosen else TEXT,
                          font=t.font, tags=tag)
            c.create_text(x + width - p(6), y + p(9), text=str(count), anchor="e", fill=TEXT_DIM, font=t.font, tags=tag)
            c.tag_bind(tag, "<Button-1>", lambda e, n=name, v=value: self._toggle(n, v))
            y += p(19)
        return y + p(8)

    def _sort_key(self, name):
        """Как сортировать значения группы."""
        if name == "purpose":
            return lambda v: rules.purpose_label(v).casefold()
        return lambda v: str(v).casefold()

    def _value_label(self, name: str, value: str) -> str:
        """Подпись значения."""
        return rules.purpose_label(value) if name == "purpose" else str(value)

    def _toggle(self, name: str, value: str) -> None:
        """Включает или выключает значение."""
        filters = self.app.s["filters"]
        chosen = list(filters.get(name, ()))
        chosen.remove(value) if value in chosen else chosen.append(value)
        if chosen:
            filters[name] = chosen
        else:
            filters.pop(name, None)
        self.app.filters_changed()
        self.redraw()

    def _reset(self) -> None:
        """Сбрасывает все фильтры."""
        self.app.s["filters"].clear()
        self.app.filters_changed()
        self.redraw()


# --------------------------------------------------------------------------------------------
# Главное окно
# --------------------------------------------------------------------------------------------
class App:
    """Главное окно: связывает интерфейс, настройки и логику из core."""

    @staticmethod
    def option_rows() -> tuple:
        """Переключатели блока «Параметры организации»: ключ, подпись, подсказка."""
        return (
            ("one_copy", tr("Одна копия плагина"), tr("Если плагин есть в нескольких форматах, копируется один. Порядок форматов задаётся в настройках.")),
            ("skip_errors", tr("Пропускать плагины с ошибками"), tr("Не копировать плагины, которые FL Studio не смог просканировать.")),
            ("skip_organized", tr("Пропускать уже организованные"),
             tr("Плагин со звездой уже лежит в Effects или Generators: повторно он не копируется.")),
            ("reorganize", tr("Перекладывать уже организованные"),
             tr("Переместить плагины со звездой в папки текущей раскладки. Отменяется кнопкой «Отменить».")),
            ("overwrite", tr("Перезаписывать существующие файлы"), tr("Заменять файл, если такой уже есть в папке вендора.")),
            ("only_filtered", tr("Только плагины из списка"),
             tr("Организовать только то, что видно в списке с учётом фильтров и поиска.")),
        )

    def __init__(self, root: tk.Tk, scale: float, settings: core.Settings, db_override: str | None = None,
                 forced_theme: str | None = None, show_event=None):
        """Загружает данные и строит окно."""
        self.root, self.s = root, settings
        self.dpi = scale
        self.motion = Motion(root, settings["animations"])
        self.curtain = Curtain()
        self.tray = None
        self.show_event = show_event
        self.last_backup = 0.0
        self.backup_running = False
        self.key_bindings: dict[str, str] = {}
        self.settings_section = "general"
        self.undo_btn = None
        self.forced_theme = forced_theme
        self.plugins: list[core.Plugin] = []
        self.sources: list[core.Source] = []
        self.folders: dict[str, dict[str, str]] = {}
        self.page = settings["side_page"] if settings["side_page"] in ("options", "plugin") else "options"
        self.selected_source: str | None = None
        self.source_offset = 0
        self.install = ""
        self.db = db_override or ""
        self.worker: threading.Thread | None = None
        self.cancel_flag = threading.Event()
        self.events: queue.Queue = queue.Queue()
        self.maximized = False
        self.normal_geometry = ""
        self.resize_state = None
        self.hint_text = ""
        self._locate_database()
        if not self.s["layout"]:
            has_user = bool(self.db) and any(os.path.isdir(os.path.join(self.db, kind, "USER")) for kind in core.KINDS)
            self.s["layout"] = rules.LAYOUTS["user_vendor" if has_user else "vendor"]
        if not self.s["layout_generators"]:
            self.s["layout_generators"] = self.s["layout"]
        self.s["format_order"] = [f for f in self.s["format_order"] if f in core.FORMAT_ORDER] + [f for f in core.FORMAT_ORDER if f not in self.s["format_order"]]
        self.s["filters"] = {k: list(v) for k, v in self.s["filters"].items() if k in rules.FIELDS and v}
        self.query = rules.parse_query("")
        self.filter_panel = None
        self.main_tab = settings["main_tab"] if settings["main_tab"] in ("plugins", "settings", "about") else "plugins"
        self.theme_path = None
        self.theme_stamp = None
        self._load_palette()
        self.t = self._make_theme()
        self._build_window()
        self.find_var.set(settings["find_text"])
        self.refresh(first=True)
        self.grid.selected = set(settings["selected"]) & {p.key for p in self.grid.items}
        if self.grid.selected:
            self.grid.show_row(settings["selected"][0])
            self._update_plugin_page()
        self.bind_hotkeys()
        self.root.after(2000, self._watch_theme)
        if show_event:
            self.root.after(400, self._watch_second_start)

    # ------------------------------------------------------------------ подготовка
    def _locate_database(self) -> None:
        """Находит базу: аргумент, настройки или автопоиск."""
        found, self.install = core.find_database()
        if not self.db:
            saved = self.s["db"]
            self.db = saved if core.is_database(saved) else found

    def _make_theme(self) -> Theme:
        """Создаёт Theme с учётом масштаба и шрифта из настроек."""
        return Theme(self.root, self.dpi * self.s["ui_scale"] / 100, self.s["font_family"], self.s["font_size"], self.motion)

    def _load_palette(self) -> None:
        """Палитра по настройке: классика, активная тема FL Studio или свои цвета."""
        mode = self.s["theme_mode"]
        self.theme_path = self.forced_theme or (fltheme.find_active_theme(self.db, self.install) if mode == "fl" else None)
        self.theme_stamp = self._theme_signature()
        if mode == "custom" and not self.forced_theme:
            globals().update(fltheme.custom_palette(self.s["custom_colors"]))
        else:
            globals().update(fltheme.build_palette(fltheme.read_theme(self.theme_path) if self.theme_path else None))

    def _theme_signature(self):
        """Отпечаток файла темы, чтобы заметить его изменение."""
        try:
            info = os.stat(self.theme_path)
            return self.theme_path, info.st_mtime_ns, info.st_size
        except (OSError, TypeError):
            return None

    def _watch_theme(self) -> None:
        """Раз в 2 секунды проверяет, не сменилась ли тема FL Studio."""
        if self.s["theme_mode"] == "fl" and not self.worker:
            current = fltheme.find_active_theme(self.db, self.install) if not self.forced_theme else self.forced_theme
            before, self.theme_path = self.theme_path, current
            if self._theme_signature() != self.theme_stamp or before != current:
                self.apply_theme()
        self.root.after(2000, self._watch_theme)

    def apply_theme(self) -> None:
        """Следует за сменой темы, если пользователь не занят другим."""
        if not self.worker and not self.root.grab_current():
            self.rebuild_ui()

    def rebuild_ui(self) -> None:
        """Перестраивает окно после смены палитры, масштаба, шрифта или языка."""
        self._save_layout()
        selected, page, anchor = set(self.grid.selected), self.page, self.grid.anchor
        if self.filter_panel:
            self.filter_panel.close()
        find = self.find_var.get()
        self._load_palette()
        self.t = self._make_theme()
        self.frame.destroy()
        self._build_window()
        self.grid.selected = selected
        self.grid.anchor = anchor
        self.find_var.set(find)
        self.page = page
        self.refresh()
        self.show_page(page)

    def set_scale(self, percent: int) -> None:
        """Меняет масштаб интерфейса и пропорционально размер окна."""
        if percent == self.s["ui_scale"]:
            return
        self._save_layout()
        old = self.t.scale
        self.s["ui_scale"] = percent
        self.s.save()
        new = self.dpi * percent / 100
        if not self.maximized:
            x, y, w, h = work_area(self.root)
            width = min(w, round(self.root.winfo_width() * new / old))
            height = min(h, round(self.root.winfo_height() * new / old))
            self.root.geometry(f"{width}x{height}")
        self.rebuild_ui()

    def apply_motion(self) -> None:
        """Включает или выключает анимации."""
        self.motion.enabled = self.s["animations"]

    def set_column_visible(self, key: str, visible: bool) -> None:
        """Показывает или скрывает колонку."""
        hidden = set(self.s["hidden_columns"])
        hidden.discard(key) if visible else hidden.add(key)
        self.s["hidden_columns"] = sorted(hidden)
        self.s.save()
        self.grid.hidden = hidden
        self.grid.rebuild()

    def _header_menu(self, event) -> None:
        """Меню колонок по правому клику на заголовке."""
        menu = self._menu()
        menu.marks = []  # Tk хранит только имя переменной, поэтому держим ссылки, пока меню открыто
        for key, label, _width in columns():
            if key not in ("fav", "name"):
                mark = tk.IntVar(menu, 0 if key in self.s["hidden_columns"] else 1)
                menu.marks.append(mark)
                menu.add_checkbutton(label=label, onvalue=1, offvalue=0, variable=mark,
                                     command=lambda k=key: self.set_column_visible(k, k in self.s["hidden_columns"]))
        menu.tk_popup(event.x_root, event.y_root)
        menu.grab_release()

    def settings_changed(self) -> None:
        """Изменились производители или правила: обновляем список и папки."""
        self.s.save()
        self._apply_vendors()
        self.update_view()
        self._update_plugin_page()

    def settings_imported(self) -> None:
        """Применяет импортированные настройки."""
        self.s["filters"] = {k: list(v) for k, v in self.s["filters"].items() if k in rules.FIELDS and v}
        self.apply_motion()
        self.bind_hotkeys()
        i18n.set_language(self.s["language"])
        self.s.save()
        self.rebuild_ui()

    def _double_click(self, plugin: core.Plugin) -> None:
        """Двойной клик по плагину: действие из настроек."""
        action = self.s["double_click"]
        if action == "plugin":
            self.show_page("plugin")
        elif action == "folder" and plugin.primary and os.path.isdir(os.path.dirname(plugin.primary.filename)):
            self._open(os.path.dirname(plugin.primary.filename))
        elif action == "star":
            self._star_click(plugin)

    # ------------------------------------------------------------------ горячие клавиши
    def bind_hotkeys(self) -> None:
        """Подключает горячие клавиши."""
        self.key_bindings = hotkeys.bindings(self.s["hotkeys"])
        self.root.bind("<KeyPress>", self._key_press)

    def _key_press(self, event) -> None:
        """Находит действие по нажатому сочетанию."""
        action = self.key_bindings.get(hotkeys.shortcut(event.keycode, event.state))
        if action and not self.root.grab_current():
            getattr(self, "_do_" + action)()
            return "break"

    def _do_organize(self) -> None:
        """Клавиша: организовать."""
        self.organize_click()

    def _do_refresh(self) -> None:
        """Клавиша: обновить список."""
        self.refresh()

    def _do_find(self) -> None:
        """Клавиша: перейти к поиску."""
        self.show_tab("plugins")
        self.find_entry.focus_set()
        self.find_entry.select_range(0, "end")

    def _do_filters(self) -> None:
        """Клавиша: открыть фильтры."""
        self.show_tab("plugins")
        self.toggle_filters()

    def _do_backup(self) -> None:
        """Клавиша: сделать бэкап."""
        self.backup_click()

    def _do_undo(self) -> None:
        """Клавиша: отменить."""
        self.undo_click()

    def _do_tab_plugins(self) -> None:
        """Клавиша: вкладка «Плагины»."""
        self.show_tab("plugins")

    def _do_tab_settings(self) -> None:
        """Клавиша: вкладка «Настройки»."""
        self.show_tab("settings")

    def _do_tab_about(self) -> None:
        """Клавиша: вкладка «О программе»."""
        self.show_tab("about")

    # ------------------------------------------------------------------ запуск
    def startup(self) -> None:
        """Когда окно на экране: первый запуск, затем выбранное действие при старте."""
        if self.s.first_run:
            import settings_page
            settings_page.Wizard(self)
            self.s.first_run = False
        action = self.s["startup_action"]
        if action == "new":
            self.s["filters"]["organized"] = ["no"]
            self.filters_changed()
        elif action == "propose" and self.db:
            self.organize_click(proposal=True)

    def _watch_second_start(self) -> None:
        """Второй запуск программы только будит это окно."""
        if ctypes.windll.kernel32.WaitForSingleObject(self.show_event, 0) == 0:
            self.restore_window()
        self.root.after(400, self._watch_second_start)

    def restore_window(self) -> None:
        """Возвращает окно из трея или свёрнутого состояния."""
        if self.tray:
            self.tray.hide()
        self.root.deiconify()
        make_app_window(self.root)
        user32.ShowWindow(hwnd_of(self.root), 9)  # SW_RESTORE: для свёрнутого окна
        self.root.lift()
        self.root.focus_force()
        if self.main_tab == "about":
            self.about.show()

    # ------------------------------------------------------------------ плавные переходы
    def fade_rect(self, x: int, y: int, w: int, h: int) -> None:
        """Плавно проявляет область окна (координаты экрана)."""
        if not self.motion.enabled or not self.root.winfo_viewable():
            return
        self.curtain.show(hwnd_of(self.root), x, y, w, h, PANEL)
        self.motion.run("curtain", 170, lambda share: self.curtain.alpha((1 - share) ** 2), self.curtain.hide)

    def _build_window(self) -> None:
        """Строит всё окно."""
        root, t = self.root, self.t
        p = t.p
        root.configure(bg=EDGE)
        self.frame = tk.Frame(root, bg=FRAME)
        self.frame.pack(fill="both", expand=True, padx=1, pady=1)
        self._build_title()
        self._build_tabs()
        self.body = tk.Frame(self.frame, bg=PANEL)
        self.left_w = p(self.s["left_width"])
        self.left = tk.Canvas(self.body, bg=PANEL, width=self.left_w, highlightthickness=0)
        self.left.pack(side="left", fill="y")
        self.left.bind("<Configure>", lambda e: self._place_bottom_buttons())
        self.split = tk.Canvas(self.body, bg=PANEL, width=p(12), highlightthickness=0, cursor="sb_h_double_arrow")
        self.split.pack(side="left", fill="y")
        self.split.bind("<Configure>", self._draw_split)
        self.split.bind("<B1-Motion>", self._split_drag)
        self.split.bind("<ButtonRelease-1>", lambda e: self._save_layout())
        right = tk.Frame(self.body, bg=PANEL)
        right.pack(side="left", fill="both", expand=True, pady=(p(6), 0))
        self.grid = Grid(right, t, self.s["column_widths"], list(self.s["sort"]), self._selection_changed, self._star_click, self._context_menu,
                         self.s["column_order"], self.s["hidden_columns"])
        self.grid.on_layout = self._save_layout
        self.grid.on_double = self._double_click
        self.grid.on_header_menu = self._header_menu
        self.grid.c.pack(fill="both", expand=True)
        self._build_bottom(right)
        self.settings_page = tk.Canvas(self.frame, bg=PANEL, highlightthickness=0)
        self.about_page = tk.Canvas(self.frame, bg=PANEL, highlightthickness=0)
        self.about = about.AboutPage(self.about_page, self.t, globals(), APP_TITLE, VERSION, lambda: self._open(PROJECT_URL))
        import settings_page
        self.settings_view = settings_page.SettingsPage(self.settings_page, self)
        self._build_left()
        self.show_tab(self.main_tab)
        self.frame.bind("<Motion>", self._edge_motion)
        self.frame.bind("<Button-1>", self._edge_press)
        self.frame.bind("<B1-Motion>", self._edge_drag)
        self.frame.bind("<ButtonRelease-1>", lambda e: self._edge_release())
        root.protocol("WM_DELETE_WINDOW", self.close)

    def _build_tabs(self) -> None:
        """Вкладки окна."""
        t = self.t
        p = t.p
        c = self.tabs = tk.Canvas(self.frame, bg=PANEL, height=p(30), highlightthickness=0)
        c.pack(fill="x", padx=p(5))
        self.tab_items = {}
        x = p(6)
        for name, label in (("plugins", tr("Плагины")), ("settings", tr("Настройки")), ("about", tr("О программе"))):
            w = t.font.measure(label) + p(22)
            rect = c.create_rectangle(x, p(5), x + w, p(30), fill=TAB_OFF, outline=TAB_LINE, tags=f"win_{name}")
            text = c.create_text(x + w // 2, p(17), text=label, fill=TEXT, font=t.font, tags=f"win_{name}")
            self.tab_items[name] = (rect, text)
            c.tag_bind(f"win_{name}", "<Button-1>", lambda e, n=name: self.show_tab(n))
            x += w

    def show_tab(self, name: str) -> None:
        """Переключает вкладку окна."""
        p = self.t.p
        if name != self.main_tab and self.tabs.winfo_viewable():
            self.fade_rect(self.frame.winfo_rootx(), self.tabs.winfo_rooty() + self.tabs.winfo_height(), self.frame.winfo_width(),
                           self.frame.winfo_rooty() + self.frame.winfo_height() - self.tabs.winfo_rooty() - self.tabs.winfo_height())
        self.main_tab = name
        pages = {"plugins": self.body, "settings": self.settings_page, "about": self.about_page}
        for key, page in pages.items():
            page.pack_forget()
            on = key == name
            rect, text = self.tab_items[key]
            self.tabs.itemconfigure(rect, fill=TAB_ON if on else TAB_OFF, outline=TAB_BORDER if on else TAB_LINE)
            self.tabs.itemconfigure(text, fill=ORANGE if on else TEXT)
            if on:
                self.tabs.tag_raise(rect)
                self.tabs.tag_raise(text)
        pages[name].pack(fill="both", expand=True, padx=p(5), pady=(0, p(5)))
        if name == "settings" and hasattr(self.settings_view, "status"):
            self.settings_view.draw_section()
        self.root.update_idletasks()
        if name == "about":
            self.about.show()
        else:
            self.about.hide()

    def _build_title(self) -> None:
        """Заголовок окна с кнопками."""
        t = self.t
        p = t.p
        c = self.title = tk.Canvas(self.frame, bg=FRAME, height=p(27), highlightthickness=0)
        c.pack(fill="x")
        c.create_text(p(7), p(14), text=APP_TITLE, anchor="w", fill=TITLE_TEXT, font=t.font_title)
        c.bind("<Button-1>", self._title_press)
        c.bind("<Double-Button-1>", lambda e: self.toggle_maximize())
        self.win_buttons = []
        for name, command in (("win_close", self.close), ("win_max", self.toggle_maximize), ("win_min", self.minimize)):
            hover = c.create_rectangle(0, 0, 0, 0, fill=FRAME, outline="")
            item = c.create_image(0, p(14), image=t.images[name])
            for target in (hover, item):
                c.tag_bind(target, "<Enter>", lambda e, h=hover: c.itemconfigure(h, fill=WIN_HOVER))
                c.tag_bind(target, "<Leave>", lambda e, h=hover: c.itemconfigure(h, fill=FRAME))
                c.tag_bind(target, "<ButtonRelease-1>", lambda e, cmd=command: cmd())
                c.tag_bind(target, "<Button-1>", lambda e: "break")
            self.win_buttons.append((hover, item))
        c.bind("<Configure>", self._place_window_buttons)

    def _place_window_buttons(self, event) -> None:
        """Ставит кнопки заголовка у правого края."""
        p = self.t.p
        x = event.width - p(14)
        for hover, item in self.win_buttons:
            self.title.coords(item, x, p(14))
            self.title.coords(hover, x - p(11), p(2), x + p(11), p(26))
            x -= p(23)

    def _title_press(self, event) -> None:
        """Перетаскивание окна за заголовок."""
        current = self.title.find_withtag("current")
        if current and any(current[0] in pair for pair in self.win_buttons):
            return
        if not self.maximized:
            begin_native_move(self.root)

    def _build_bottom(self, parent: tk.Misc) -> None:
        """Нижняя строка: статус, фильтр и поиск."""
        t = self.t
        p = t.p
        c = self.bottom = tk.Canvas(parent, bg=PANEL, height=p(38), highlightthickness=0)
        c.pack(fill="x")
        self.status_id = c.create_text(p(1), p(19), text="", anchor="w", fill=TEXT_SOFT, font=t.font_bold)
        self.find_label = c.create_text(0, p(19), text=tr("Поиск"), anchor="e", fill=TEXT_SOFT, font=t.font_bold)
        self.filter_btn = Button(c, t, 0, p(7), p(30), p(24), "", self.toggle_filters)
        self.filter_icon = c.create_image(0, p(19), image=t.images["filter"], state="disabled")
        self.filter_badge = c.create_text(0, p(19), text="", anchor="e", fill=ORANGE, font=t.font_bold)
        for sequence, text in (("<Enter>", tr("Фильтры")), ("<Leave>", "")):
            c.tag_bind(self.filter_btn.tag, sequence, lambda e, v=text: self.set_hint(v), add="+")
        self.find_var = tk.StringVar()
        entry = self.find_entry = tk.Entry(c, textvariable=self.find_var, bg=ROW_B, fg=TEXT, insertbackground=TEXT,
                                           relief="flat", font=t.font_big, highlightthickness=1, highlightbackground=FIND_LINE,
                                           highlightcolor=FOCUS, selectbackground=SELECT, selectforeground=WHITE)
        self.find_window = c.create_window(0, p(19), anchor="e", window=entry, width=p(207), height=p(24))
        self.find_var.trace_add("write", lambda *a: self.update_view())
        entry.bind("<Escape>", lambda e: self.find_var.set(""))
        c.bind("<Configure>", self._place_find)
        self.root.bind("<Control-f>", lambda e: (entry.focus_set(), entry.select_range(0, "end")))

    def _place_find(self, event) -> None:
        """Размещает поиск и фильтр у правого края."""
        p = self.t.p
        self.bottom.coords(self.find_window, event.width - p(1), p(19))
        self.bottom.coords(self.find_label, event.width - p(214), p(19))
        x = event.width - p(214) - self.t.font_bold.measure(tr("Поиск")) - p(12) - p(30)
        self.bottom.coords(self.filter_btn.image, x, p(7))
        self.bottom.coords(self.filter_icon, x + p(15), p(19))
        self.bottom.coords(self.filter_badge, x - p(6), p(19))
        self._render_status()

    def _draw_split(self, event) -> None:
        """Точки на разделителе панелей."""
        c, p = self.split, self.t.p
        c.delete("all")
        cy = event.height // 2
        for i in range(4):
            y = cy - p(6) + i * p(4)
            c.create_rectangle(p(4), y, p(6), y + p(2), fill=DOTS, outline="")

    def _split_drag(self, event) -> None:
        """Меняет ширину левой панели."""
        p = self.t.p
        width = self.split.winfo_rootx() + event.x - self.body.winfo_rootx()
        width = max(p(270), min(p(520), width))
        if width != self.left_w:
            self.left_w = width
            self.left.configure(width=width)
            self._build_left()

    # ------------------------------------------------------------------ левая панель
    def _group(self, y: int, h: int, title: str, tag: str, text_x: int = 3, x0: int | None = None, x1: int | None = None) -> None:
        """Рамка группы со скошенным заголовком."""
        c, t = self.paint, self.t
        p = t.p
        x0 = p(6) if x0 is None else x0
        x1 = self.left_w - p(6) if x1 is None else x1
        head_h = p(20)
        c.create_rectangle(x0, y, x1, y + h, fill=GROUP, outline="", tags=tag)
        tw = t.font.measure(title)
        tx = x0 + p(text_x)
        notch = tx + tw + p(4)
        c.create_polygon(x0, y, notch + p(8), y, notch, y + head_h, x0, y + head_h, fill=GROUP_HEAD, outline="", tags=tag)
        c.create_line(x0, y + head_h, notch, y + head_h, notch + p(8), y, fill=GROUP_LINE, tags=tag)
        c.create_line(notch + p(8), y, x1, y, fill=GROUP_HEAD, tags=tag)
        c.create_line(x0, y + h, x1, y + h, fill=GROUP_LINE, tags=tag)
        c.create_text(tx, y + head_h // 2, text=title, anchor="w", fill=TEXT, font=t.font, tags=tag)

    def _led(self, x, y, label, key, tag, hint="", command=None) -> None:
        """Индикатор-переключатель настройки key."""
        c, t = self.paint, self.t
        p = t.p
        click = f"led_{key}"
        image = c.create_image(x, y, anchor="w", image=t.images["led_on" if self.s[key] else "led_off"], tags=(tag, click))
        c.create_text(x + p(18), y, text=label, anchor="w", fill=TEXT_SOFT, font=t.font, tags=(tag, click))

        def toggle(_event):
            """Переключает настройку."""
            self.s[key] = not self.s[key]
            frames = t.led_frames() if self.motion.enabled else [t.images["led_off"], t.images["led_on"]]
            steps = frames if self.s[key] else frames[::-1]
            self.motion.run(click, 110, lambda share: c.itemconfigure(image, image=steps[min(len(steps) - 1, int(share * len(steps)))]))
            if command:
                command()
            self.s.save()

        c.tag_bind(click, "<Button-1>", toggle)
        if hint:
            c.tag_bind(click, "<Enter>", lambda e: self.set_hint(hint))
            c.tag_bind(click, "<Leave>", lambda e: self.set_hint(""))

    def _box(self, x0, y0, x1, y1, tag) -> None:
        """Поле с рамкой на левой панели."""
        self.left.create_rectangle(x0, y0, x1, y1, fill=BOX, outline=BOX_LINE, tags=tag)

    def _build_left(self) -> None:
        """Левая панель: главная кнопка, вкладки и страницы."""
        self.paint = self.left
        c, t = self.left, self.t
        p = t.p
        c.delete("all")
        self.main_btn = Button(c, t, p(6), p(7), self.left_w - p(12), p(29), tr("Организовать плагины"), self.organize_click)
        self.tab_ids = {}
        x = p(6)
        y0, y1 = p(52), p(81)
        for page, label in (("options", tr("Параметры")), ("plugin", tr("Плагин"))):
            w = t.font.measure(label) + p(14)
            rect = c.create_rectangle(x, y0, x + w, y1, fill=TAB_OFF, outline=TAB_LINE, tags=f"tab_{page}")
            text = c.create_text(x + w // 2, (y0 + y1) // 2, text=label, fill=TEXT, font=t.font, tags=f"tab_{page}")
            self.tab_ids[page] = (rect, text)
            c.tag_bind(f"tab_{page}", "<Button-1>", lambda e, pg=page: self.show_page(pg))
            x += w
        self._led(self.left_w - p(24) - t.font.measure(tr("Предпросмотр")), p(66), tr("Предпросмотр"), "preview", "top_led",
                  tr("Перед копированием показывать, что и куда будет скопировано."))
        self._build_options_page()
        self._build_plugin_page()
        self.show_page(self.page)
        if self.worker:
            self.main_btn.set_text(tr("Отмена"))

    def _build_options_page(self) -> None:
        """Страница «Параметры»."""
        c, t = self.left, self.t
        p = t.p
        tag = "p_options"
        x0, x1 = p(6), self.left_w - p(6)
        y = p(89)
        self._group(y, p(59), tr("База плагинов FL Studio"), tag)
        self.db_btn_folder = Button(c, t, x0 + p(6), y + p(29), p(34), p(23), "", self.choose_database, tags=(tag,))
        c.create_image(x0 + p(23), y + p(40), image=t.images["folder"], state="disabled", tags=tag)
        self.db_text = c.create_text(x0 + p(47), y + p(40), text="", anchor="w", fill=TEXT, font=t.font, tags=tag)
        c.tag_bind(self.db_text, "<Enter>", lambda e: self.set_hint(self.db or ""))
        c.tag_bind(self.db_text, "<Leave>", lambda e: self.set_hint(""))
        y += p(67)
        rows = self.source_rows = 10
        list_h = rows * p(19) + p(4)
        h = p(27) + list_h + p(6)
        self._group(y, h, tr("Источники плагинов"), tag, text_x=46)
        add = c.create_image(x0 + p(4), y + p(10), anchor="w", image=t.images["folder_plus"], tags=(tag, "src_add"))
        rem = c.create_image(x0 + p(25), y + p(10), anchor="w", image=t.images["folder_x"], tags=(tag, "src_rem"))
        c.tag_bind(add, "<Button-1>", lambda e: self.add_custom_source())
        c.tag_bind(rem, "<Button-1>", lambda e: self.remove_custom_source())
        c.tag_bind(add, "<Enter>", lambda e: self.set_hint(tr("Добавить свою папку с файлами .fst и .nfo.")))
        c.tag_bind(rem, "<Enter>", lambda e: self.set_hint(tr("Убрать выбранную свою папку из списка.")))
        for item in (add, rem):
            c.tag_bind(item, "<Leave>", lambda e: self.set_hint(""))
        self.src_box = (x0 + p(6), y + p(27), x1 - p(6), y + p(27) + list_h)
        self._box(*self.src_box, (tag, "src_frame"))
        c.bind("<MouseWheel>", self._source_wheel)
        self._draw_sources()
        y += h + p(8)
        self._group(y, p(56), tr("Раскладка папок"), tag)
        self.layout_btn = Button(c, t, x0 + p(6), y + p(26), x1 - x0 - p(12), p(24), "", self.layout_menu, tags=(tag,))
        c.create_image(x1 - p(16), y + p(38), image=t.images["caret"], state="disabled", tags=tag)
        y += p(62)
        rows = self.option_rows()
        options_h = p(26) + len(rows) * p(21) + p(9)
        self._group(y, options_h, tr("Параметры организации"), tag)
        for i, (key, label, hint) in enumerate(rows):
            self._led(x0 + p(14), y + p(32) + i * p(21), label, key, tag, hint)
        self._update_layout_label()
        self._update_db_label()

    def _update_db_label(self) -> None:
        """Показывает путь к базе."""
        p = self.t.p
        width = self.left_w - p(66)
        text = self.t.fit((self.db + "\\") if self.db else tr("Папка не найдена: выберите её"), width, middle=True)
        self.left.itemconfigure(self.db_text, text=text, fill=TEXT if self.db else ORANGE)

    def _draw_sources(self) -> None:
        """Рисует видимые строки источников."""
        c, t = self.left, self.t
        p = t.p
        c.delete("srcrow")
        x0, y0, x1, _ = self.src_box
        state = "normal" if self.page == "options" else "hidden"
        visible = self.sources[self.source_offset:self.source_offset + self.source_rows]
        disabled = set(self.s["disabled_sources"] or [])
        for r, source in enumerate(visible):
            y = y0 + p(2) + r * p(19) + p(9)
            tag = ("srcrow", "p_options", f"src_{r}")
            selected = source.id == self.selected_source
            ink = ORANGE if selected else TEXT
            enabled = source.id not in disabled
            # Рисуется первым: вся строка кликабельна, в том числе промежутки между подписями.
            c.create_rectangle(x0 + 1, y - p(9), x1 - 1, y + p(9), fill=BOX, outline="", state=state, tags=tag)
            if enabled:
                c.create_image(x0 + p(11), y, image=t.images["check"], state=state, tags=tag)
            c.create_text(x0 + p(24), y, text=source.label, anchor="w", fill=ink if enabled else TEXT_OFF, font=t.font, state=state, tags=tag)
            count = str(source.count)
            count_x = x1 - p(7)
            c.create_text(count_x, y, text=count, anchor="e", fill=TEXT_DIM if enabled else TEXT_OFF, font=t.font, state=state, tags=tag)
            path_x = x0 + p(64)
            room = count_x - t.font.measure(count) - p(6) - path_x
            c.create_text(path_x, y, text=t.fit(source.path, room, middle=True), anchor="w",
                          fill=ink if enabled else TEXT_OFF, font=t.font, state=state, tags=tag)
            c.tag_bind(f"src_{r}", "<Button-1>", lambda e, s=source: self._source_click(e, s))
        if not self.sources:
            c.create_text(x0 + p(10), y0 + p(12), text=tr("Источники не найдены"), anchor="w", fill=TEXT_DIM, font=t.font,
                          state=state, tags=("srcrow", "p_options"))

    def _source_wheel(self, event) -> None:
        """Прокрутка источников колесом."""
        x0, y0, x1, y1 = self.src_box
        if self.page != "options" or not (x0 <= event.x <= x1 and y0 <= event.y <= y1):
            return
        maximum = max(0, len(self.sources) - self.source_rows)
        offset = max(0, min(maximum, self.source_offset + (-1 if event.delta > 0 else 1)))
        if offset != self.source_offset:
            self.source_offset = offset
            self._draw_sources()

    def _source_click(self, event, source: core.Source) -> None:
        """Клик по источнику: выбор или включение."""
        check_area = self.src_box[0] + self.t.p(22)
        self.left.delete("src_focus")
        x0, y0, x1, y1 = self.src_box
        self.t.soft_frame(self.left, (x0, y0, x1 + 1, y1 + 1), FOCUS, GROUP, self.t.p(2), ("src_focus", "p_options"))
        self.grid.on_focus = lambda: self.left.delete("src_focus")
        self.selected_source = source.id
        if event.x < check_area:
            disabled = set(self.s["disabled_sources"] or [])
            disabled.symmetric_difference_update({source.id})
            self.s["disabled_sources"] = sorted(disabled)
            self.s.save()
            self.update_view()
        self._draw_sources()

    def _build_plugin_page(self) -> None:
        """Страница «Плагин»."""
        c, t = self.left, self.t
        p = t.p
        tag = "p_plugin"
        x0, x1 = p(6), self.left_w - p(6)
        label_x = x0 + p(6)
        y = p(89)
        self._group(y, p(194), tr("Инфо"), tag)
        field_x = x0 + p(62)
        self.fields = {}

        def label(y_pos, text):
            """Подпись поля."""
            c.create_text(label_x, y_pos, text=text, anchor="w", fill=TEXT, font=t.font, tags=tag)

        def field(y_pos, key, x_from=field_x):
            """Поле со значением."""
            self._box(x_from, y_pos - p(12), x1 - p(7), y_pos + p(12), tag)
            self.fields[key] = c.create_text(x_from + p(5), y_pos, text="", anchor="w", fill=TEXT, font=t.font_big, tags=tag)

        label(y + p(40), tr("Имя"))
        field(y + p(40), "name")
        label(y + p(67), tr("Статус"))
        self.fields["status"] = c.create_text(field_x + p(2), y + p(67), text="", anchor="w", fill=TEXT, font=t.font, tags=tag)
        label(y + p(94), tr("Тип"))
        self._box(field_x, y + p(83), field_x + p(88), y + p(105), tag)
        self.fields["type"] = c.create_text(field_x + p(5), y + p(94), text="", anchor="w", fill=TEXT_OFF, font=t.font, tags=tag)
        label(y + p(121), tr("Вендор"))
        self.vendor_var = tk.StringVar()
        self.vendor_entry = tk.Entry(c, textvariable=self.vendor_var, bg=BOX, fg=TEXT, insertbackground=TEXT, relief="flat",
                                     font=t.font_big, highlightthickness=1, highlightbackground=BOX_LINE, highlightcolor=FOCUS,
                                     selectbackground=SELECT, selectforeground=WHITE, disabledbackground=BOX, disabledforeground=TEXT_OFF)
        self.vendor_window = c.create_window(field_x, y + p(121), anchor="w", window=self.vendor_entry, width=x1 - p(7) - field_x, height=p(24), tags=tag)
        self.vendor_entry.bind("<Return>", lambda e: self.apply_vendor())
        self.vendor_var.trace_add("write", lambda *a: self._vendor_changed())
        label(y + p(147), tr("Файл пресета"))
        field(y + p(172), "preset", label_x)
        y += p(202)
        self._group(y, p(89), "", tag, text_x=23)
        self.star_led = c.create_image(x0 + p(4), y + p(10), anchor="w", image=t.images["led_off"], tags=(tag, "org_led"))
        c.create_text(x0 + p(23), y + p(10), text=tr("Организован"), anchor="w", fill=TEXT, font=t.font, tags=(tag, "org_led"))
        c.tag_bind("org_led", "<Button-1>", lambda e: self._star_selected())
        label(y + p(40), tr("Папка"))
        field(y + p(40), "folder")
        label(y + p(67), tr("Для чего"))
        field(y + p(67), "purpose")
        c.itemconfigure(self.fields["purpose"], font=t.font)
        for item in c.find_overlapping(field_x + p(1), y + p(58), x1 - p(8), y + p(76)):
            c.addtag_withtag("purpose_box", item)
        c.create_image(x1 - p(17), y + p(67), image=t.images["caret"], state="disabled", tags=tag)
        c.tag_bind("purpose_box", "<Button-1>", self._purpose_menu)
        y += p(97)
        combined_h = p(150)
        self._group(y, combined_h, tr("Форматы плагина"), tag)
        self.combo_box = (label_x, y + p(28), x1 - p(7), y + combined_h - p(7))
        self._box(*self.combo_box, tag)
        bx0, by0, bx1, _ = self.combo_box
        c.create_rectangle(bx0 + 1, by0 + 1, bx1, by0 + p(19), fill=HEADER, outline="", tags=tag)
        self.combo_x = (bx0 + p(4), bx0 + p(54), bx0 + p(104))
        for x, text in zip(self.combo_x, (tr("Формат"), tr("Бит"), tr("Файл"))):
            c.create_text(x, by0 + p(10), text=text, anchor="w", fill=TEXT_DIM, font=t.font, tags=tag)
        w = (self.left_w - p(12) - p(6)) // 2
        self.apply_btn = Button(c, t, 0, 0, round(w * 1.2), p(28), tr("Применить"), self.apply_vendor, tags=(tag, "bottom_btn"))
        self.reset_btn = Button(c, t, 0, 0, round(w * 0.8), p(28), tr("Сбросить"), self.reset_vendor, tags=(tag, "bottom_btn"))
        self._place_bottom_buttons()
        self._update_plugin_page()

    def _place_bottom_buttons(self) -> None:
        """Прижимает кнопки вниз панели."""
        if not hasattr(self, "apply_btn"):
            return
        c, p = self.left, self.t.p
        y = c.winfo_height() - p(35)
        if y < p(545):
            y = p(545)
        for button, x in ((self.apply_btn, p(6)), (self.reset_btn, p(6) + self.apply_btn.w + p(6))):
            c.coords(button.image, x, y)
            c.coords(button.label, x + button.w // 2, y + button.h // 2)

    def show_page(self, page: str) -> None:
        """Переключает страницу левой панели."""
        self.page = page
        c = self.left
        for name, (rect, text) in self.tab_ids.items():
            on = name == page
            c.itemconfigure(rect, fill=TAB_ON if on else TAB_OFF, outline=TAB_BORDER if on else TAB_LINE)
            if on:
                c.tag_raise(rect)
                c.tag_raise(text)
            c.itemconfigure(text, fill=ORANGE if on else TEXT)
        c.itemconfigure("p_options", state="normal" if page == "options" else "hidden")
        c.itemconfigure("p_plugin", state="normal" if page == "plugin" else "hidden")
        # Встроенные виджеты скрытой страницы нужно прятать отдельно.
        c.itemconfigure(self.vendor_window, state="normal" if page == "plugin" else "hidden")
        if page == "plugin":
            self._update_plugin_page()
            c.itemconfigure("combo", state="normal")

    def _update_plugin_page(self) -> None:
        """Заполняет страницу «Плагин» по выбору в списке."""
        if not hasattr(self, "fields"):
            return
        c, t = self.left, self.t
        p = t.p
        selection = self.grid.selection()
        plugin = selection[0] if selection else None
        room = self.left_w - p(82)

        def put(key, value, width=room, middle=False):
            """Записывает значение в поле."""
            c.itemconfigure(self.fields[key], text=t.fit(value, width, middle))

        c.delete("combo")
        if plugin is None:
            for key in ("name", "status", "type", "preset", "folder", "purpose"):
                put(key, "")
            self.vendor_var.set("")
            self.vendor_entry.configure(state="disabled")
            self.apply_btn.set_enabled(False)
            self.reset_btn.set_enabled(False)
            c.itemconfigure(self.star_led, image=t.images["led_off"])
            return
        many = len(selection) > 1
        self.vendor_entry.configure(state="normal")
        put("name", tr("Выбрано: {items}").format(items=plugins_word(len(selection))) if many else plugin.name)
        put("status", "ok" if plugin.ok else tr("ошибка"))
        put("type", "?" if not plugin.type_known and not plugin.ok else tr("Эффект") if plugin.kind == "Effects" else tr("Синтезатор"))
        preset = os.path.relpath(plugin.fst, self.db) if plugin.fst and self.db and not plugin.source.startswith("custom:") else (plugin.fst or tr("нет файла"))
        put("preset", preset, self.left_w - p(32), middle=True)
        target = self._relative_target(plugin)
        put("folder", target, room, middle=True)
        put("purpose", rules.purpose_label(plugin.purposes[0]) if plugin.purposes else "", room - p(20))
        c.itemconfigure(self.star_led, image=t.images["led_on" if plugin.organized_in else "led_off"])
        self.loading_vendor = True
        self.vendor_var.set(plugin.vendor if not many or len({x.vendor for x in selection}) == 1 else "")
        self.loading_vendor = False
        self.apply_btn.set_enabled(False)
        self.reset_btn.set_enabled(plugin.name_id in self.s["vendor_overrides"] or many)
        bx0, by0, bx1, by1 = self.combo_box
        state = "normal" if self.page == "plugin" else "hidden"
        for r, item in enumerate(plugin.files[:7]):
            y = by0 + p(29) + r * p(19)
            if y + p(9) > by1:
                break
            values = (item.format, item.bits, t.fit(item.filename, bx1 - self.combo_x[2] - p(6), middle=True))
            for x, value in zip(self.combo_x, values):
                c.create_text(x, y, text=value, anchor="w", fill=TEXT, font=t.font, state=state, tags=("combo", "p_plugin"))

    def _relative_target(self, plugin: core.Plugin) -> str:
        """Папка плагина относительно базы."""
        if not self.db:
            return ""
        folder = plugin.organized_in or core.target_folder(self.db, plugin, self._options(), self.folders)
        try:
            return os.path.relpath(folder, self.db)
        except ValueError:
            return folder

    def _vendor_changed(self) -> None:
        """Текст производителя изменён: можно применить."""
        if getattr(self, "loading_vendor", False) or not hasattr(self, "apply_btn"):
            return
        self.apply_btn.set_enabled(bool(self.grid.selection()))

    # ------------------------------------------------------------------ данные
    def _options(self) -> core.Options:
        """Собирает параметры раскладки из настроек."""
        s = self.s
        return core.Options(one_copy=s["one_copy"], skip_errors=s["skip_errors"], skip_organized=s["skip_organized"],
                            overwrite=s["overwrite"], reorganize=s["reorganize"], layout=s["layout"] or "{vendor}",
                            generators_layout=s["layout_generators"], format_order=tuple(s["format_order"]),
                            folder_language=s["folder_language"], strip_suffix=s["strip_suffix"], move_from_new=s["move_from_new"])

    def refresh(self, first: bool = False) -> None:
        """Перечитывает базу с диска и обновляет окно."""
        plugins, sources = [], []
        error = ""
        if self.db:
            try:
                plugins, sources = core.load_installed(self.db, self.install)
            except OSError as exc:
                error = exc.strerror or str(exc)
        for folder in list(self.s["custom_sources"]):
            custom, source = core.load_custom(folder, self.install)
            plugins.extend(custom)
            sources.append(source)
        self.plugins, self.sources = plugins, sources
        if self.s["disabled_sources"] is None:
            self.s["disabled_sources"] = []
        self._apply_vendors()
        self._mark_organized()
        self.source_offset = min(self.source_offset, max(0, len(sources) - self.source_rows))
        if hasattr(self, "src_box"):
            self._draw_sources()
        self.update_view()
        self._update_plugin_page()
        self._update_undo_button()
        if error:
            self.set_hint(tr("Не удалось прочитать базу: {error}").format(error=error))

    def _apply_vendors(self) -> None:
        """Считает производителя и назначение каждого плагина."""
        overrides = self.s["vendor_overrides"]
        aliases = {source.casefold(): target for source, target in self.s["vendor_aliases"].items()}
        purpose_overrides = self.s["purpose_overrides"]
        purpose_rules = rules.load_rules(self.s["purpose_rules"])
        for p in self.plugins:
            p.vendor = overrides.get(p.name_id) or rules.apply_alias(p.raw_vendor, aliases) or (core.UNKNOWN_VENDOR if p.ok else "")
            p.vendor_edited = p.name_id in overrides
            p.purposes, p.purpose_source = rules.classify(p, purpose_overrides, purpose_rules)
            labels = " ".join(rules.purpose_label(x) for x in p.purposes)
            p.search = f"{p.name} {p.vendor} {p.filename} {p.formats} {labels}".casefold()

    def _mark_organized(self) -> None:
        """Отмечает плагины, уже разложенные по папкам."""
        organized, self.folders = core.scan_organized(self.db) if self.db else ({}, {})
        for p in self.plugins:
            p.organized_in = organized.get((p.kind, p.name_id))

    def source_plugins(self) -> list[core.Plugin]:
        """Плагины из включённых источников."""
        disabled = set(self.s["disabled_sources"] or [])
        return [p for p in self.plugins if p.source not in disabled]

    def update_view(self) -> None:
        """Применяет поиск и фильтры к списку."""
        self.query = rules.parse_query(self.find_var.get())
        filters = self.s["filters"]
        items = [p for p in self.source_plugins() if self.query.matches(p, filters)]
        self._update_filter_button()
        grid = self.grid
        grid.items = items
        grid.apply_sort()
        grid.selected &= {p.key for p in items}
        grid.set_items(items)
        self._render_status()

    def active_plugins(self) -> list[core.Plugin]:
        """С чем работает раскладка: видимый список или все включённые источники."""
        return list(self.grid.items) if self.s["only_filtered"] else self.source_plugins()

    def filters_changed(self) -> None:
        """Фильтры изменились."""
        self.update_view()
        self.s.save()

    def _update_filter_button(self) -> None:
        """Значок фильтра и число активных условий."""
        if not hasattr(self, "filter_btn"):
            return
        active = sum(len(v) for v in self.s["filters"].values())
        self.bottom.itemconfigure(self.filter_badge, text=str(active) if active else "")
        self.bottom.itemconfigure(self.filter_icon, image=self.t.images["filter_on" if active else "filter"])

    def language_menu(self) -> None:
        """Меню языков."""
        menu = self._menu()
        for code, name in i18n.available().items():
            menu.add_command(label=name, command=lambda c=code: self.set_language(c))
        menu.tk_popup(self.root.winfo_pointerx(), self.root.winfo_pointery())
        menu.grab_release()

    def set_language(self, code: str) -> None:
        """Меняет язык без перезапуска."""
        if code == i18n.LANG or self.worker:
            return
        self.s["language"] = code
        self.s.save()
        i18n.set_language(code)
        self.rebuild_ui()

    def toggle_filters(self) -> None:
        """Открывает или закрывает меню фильтров."""
        if self.filter_panel:
            self.filter_panel.close()
            return
        box = self.bottom.bbox(self.filter_btn.image)
        right = self.bottom.winfo_rootx() + self.bottom.winfo_width()
        bottom = self.bottom.winfo_rooty() + box[1] - self.t.p(4)
        self.filter_panel = FilterPanel(self, right, bottom)

    # ------------------------------------------------------------------ раскладки и назначения
    def _layout_label(self, template: str) -> str:
        """Подпись раскладки по её шаблону."""
        key = next((k for k, v in rules.LAYOUTS.items() if v == template), None)
        return tr(rules.LAYOUT_LABELS[key]) if key else template

    def _update_layout_label(self) -> None:
        """Подпись на кнопке раскладки."""
        effects, generators = self.s["layout"], self.s["layout_generators"]
        label = self._layout_label(effects)
        if generators != effects:
            label += "  |  " + self._layout_label(generators)
        self.layout_btn.set_text(self.t.fit(label, self.left_w - self.t.p(60)))

    def layout_menu(self) -> None:
        """Меню раскладок: для всех, для эффектов, для генераторов."""
        menu = self._menu()
        for title, key in ((tr("Все плагины"), "all"), (tr("Эффекты"), "layout"), (tr("Генераторы"), "layout_generators")):
            sub = self._menu(menu)
            for name in rules.LAYOUTS:
                sub.add_command(label=tr(rules.LAYOUT_LABELS[name]), command=lambda v=rules.LAYOUTS[name], k=key: self.set_layout(v, k))
            sub.add_separator()
            sub.add_command(label=tr("Свой шаблон…"), command=lambda k=key: self.custom_layout(k))
            menu.add_cascade(label=title, menu=sub)
        menu.tk_popup(self.root.winfo_pointerx(), self.root.winfo_pointery())
        menu.grab_release()

    def custom_layout(self, key: str = "all") -> None:
        """Окно своего шаблона. key: для каких плагинов."""
        text = tr("Части пути: {vendor} {purpose} {format} {bits} {letter} {kind}. Уровни разделяются знаком \\.\nПример: USER\\{purpose}\\{vendor}")
        current = self.s["custom_layout"] or self.s["layout"]
        dialog = Dialog(self.root, self.t, tr("Свой шаблон"), text, [tr("Применить"), tr("Отмена")], entry=current, width=520)
        if dialog.result != 0:
            return
        template = dialog.text.strip()
        problems = rules.layout_tokens(template)
        if problems:
            detail = problems.get("unknown", tr("шаблон пуст"))
            Dialog(self.root, self.t, tr("Ошибка"), tr("Шаблон не подходит: {detail}.").format(detail=detail), [tr("Понятно")])
            return
        self.s["custom_layout"] = template
        self.set_layout(template, key)

    def set_layout(self, template: str, key: str = "all") -> None:
        """Применяет шаблон. key: all, layout или layout_generators."""
        if key in ("all", "layout"):
            self.s["layout"] = template
        if key in ("all", "layout_generators"):
            self.s["layout_generators"] = template
        self.s.save()
        self._update_layout_label()
        self._update_plugin_page()

    def _purpose_menu(self, _event=None) -> None:
        """Меню назначения для выбранных плагинов."""
        if self.grid.selection():
            self._purpose_popup().tk_popup(self.root.winfo_pointerx(), self.root.winfo_pointery())

    def _purpose_popup(self, parent=None) -> tk.Menu:
        """Создаёт меню назначений."""
        menu = self._menu(parent)
        for purpose in sorted(rules.PURPOSES, key=lambda x: rules.purpose_label(x).casefold()):
            menu.add_command(label=rules.purpose_label(purpose), command=lambda v=purpose: self.set_purpose(v))
        menu.add_separator()
        menu.add_command(label=tr("Определять автоматически"), command=lambda: self.set_purpose(None))
        return menu

    def set_purpose(self, purpose: str | None) -> None:
        """Назначает вручную; None возвращает автоопределение."""
        selection = self.grid.selection()
        overrides = self.s["purpose_overrides"]
        for p in selection:
            if purpose:
                overrides[p.name_id] = purpose
            else:
                overrides.pop(p.name_id, None)
        self._after_vendor_edit(selection)

    def _menu(self, parent=None) -> tk.Menu:
        """Меню в цветах программы."""
        return tk.Menu(parent or self.root, tearoff=0, bg=GROUP, fg=TEXT, activebackground=SELECT, activeforeground=WHITE, bd=0,
                       font=self.t.font, relief="flat")

    # ------------------------------------------------------------------ бэкапы
    def _backup_before_change(self, small: bool = False) -> bool:
        """Автобэкап перед изменением. False значит, что он не удался и менять ничего нельзя.

        small: изменение одного плагина кликом. Серия кликов делит один бэкап на минуту,
        иначе несколько десятков кликов вытеснили бы все старые бэкапы.
        """
        if not self.s["auto_backup"] or (small and time.time() - self.last_backup < 60):
            return True
        try:
            self._make_backup()
            self.set_hint("")
            return True
        except (OSError, ValueError) as exc:
            self.set_hint("")
            Dialog(self.root, self.t, tr("Ошибка"), tr("Не удалось создать бэкап, изменение отменено: {error}").format(error=exc), [tr("Понятно")])
            return False

    def _make_backup(self) -> str:
        """Создаёт ZIP в фоновом потоке: это занимает секунды, а окно должно отвечать."""
        box: dict = {}

        def work():
            """Работа потока."""
            try:
                box["path"] = core.backup_database(self.db, self.s.backups, self.s["backup_keep"])
            except (OSError, ValueError) as exc:
                box["error"] = exc

        finished = tk.BooleanVar(self.root, False)

        def wait():
            """Ждёт конца потока, не останавливая окно."""
            if self.worker and self.worker.is_alive():
                self.root.after(30, wait)
            else:
                finished.set(True)
        self.set_hint(tr("Создаётся бэкап…"))
        self.backup_running = True
        self.worker = threading.Thread(target=work, daemon=True)
        self.worker.start()
        wait()
        self.root.wait_variable(finished)
        self.worker = None
        self.backup_running = False
        if "error" in box:
            raise box["error"]
        self.last_backup = time.time()
        self.s.log.write("backup", box["path"])
        return box["path"]

    def backup_click(self) -> None:
        """Кнопка «Бэкап»."""
        if not self.db or self.worker:
            return
        try:
            path = self._make_backup()
            self.set_hint(tr("Бэкап сохранён: {name}").format(name=os.path.basename(path)))
            if self.main_tab == "settings":
                self.settings_view.draw_section()
        except (OSError, ValueError) as exc:
            self.hint_text = ""
            Dialog(self.root, self.t, tr("Ошибка"), str(exc), [tr("Понятно")])
        self.root.after(6000, lambda: self.set_hint(""))

    def restore_click(self) -> None:
        """Кнопка «Восстановить»: меню бэкапов."""
        if not self.db or self.worker:
            return
        backups = core.list_backups(self.s.backups)
        if not backups:
            self.set_hint(tr("Бэкапов пока нет."))
            return
        menu = self._menu()
        for path in backups[:self.s["backup_keep"]]:
            stamp = time.strftime("%d.%m.%Y %H:%M:%S", time.localtime(os.path.getmtime(path)))
            size = os.path.getsize(path) / 1048576
            menu.add_command(label=f"{stamp}  ({size:.1f} MB)", command=lambda v=path: self._restore(v))
        menu.tk_popup(self.root.winfo_pointerx(), self.root.winfo_pointery())
        menu.grab_release()

    def _restore(self, path: str) -> None:
        """Восстанавливает выбранный бэкап."""
        message = tr("Вернуть папки Effects и Generators к этому бэкапу?\n\nФайлы, которых в нём нет, уйдут в корзину. Перед этим создаётся ещё один бэкап. Папка Installed не меняется.")
        if self.s["confirm_restore"] and Dialog(self.root, self.t, tr("Восстановить"), message, [tr("Восстановить"), tr("Отмена")]).result != 0:
            return
        try:
            count = core.restore_backup(path, self.db, self.s.backups, keep=self.s["backup_keep"])
            self.s.log.write("restore", f"{path}: {count}")
            self.set_hint(tr("Восстановлено файлов: {count}.").format(count=count))
        except (OSError, ValueError, core.zipfile.BadZipFile) as exc:
            Dialog(self.root, self.t, tr("Ошибка"), str(exc), [tr("Понятно")])
        self.refresh()
        self.root.after(6000, lambda: self.set_hint(""))

    # ------------------------------------------------------------------ строка состояния
    def set_hint(self, text: str) -> None:
        """Текст в строке подсказок."""
        self.hint_text = text
        self._render_status()

    def _render_status(self) -> None:
        """Показывает подсказку или счётчик плагинов."""
        if not hasattr(self, "status_id"):
            return
        t, p = self.t, self.t.p
        if self.hint_text:
            text = self.hint_text
        else:
            items = self.grid.items
            organized = sum(1 for x in items if x.organized_in)
            text = plugins_word(len(items))
            total = len(self.source_plugins())
            if len(items) != total:
                text = tr("{shown} из {total}").format(shown=text, total=total)
            if organized:
                text += tr(", организовано: {count}").format(count=organized)
        room = self.bottom.winfo_width() - p(340)
        self.bottom.itemconfigure(self.status_id, text=t.fit(text, max(room, p(100))))
        if hasattr(self, "settings_view") and hasattr(self.settings_view, "status"):
            self.settings_view.set_status(self.hint_text)

    # ------------------------------------------------------------------ выбор и действия со строками
    def _selection_changed(self) -> None:
        """Выбор в списке изменился."""
        if self.page == "plugin":
            self._update_plugin_page()

    def _star_selected(self) -> None:
        """Звезда для выбранного плагина."""
        selection = self.grid.selection()
        if selection:
            self._star_click(selection[0])

    def _star_click(self, plugin: core.Plugin) -> None:
        """Звезда: кладёт копию или убирает её."""
        if self.worker:
            return
        if plugin.organized_in:
            self._remove_plugins([plugin])
        else:
            self._copy_plugins([plugin])

    def _copy_plugins(self, plugins: list[core.Plugin]) -> None:
        """Копирует отдельные плагины в их папки."""
        opts = dataclasses.replace(self._options(), one_copy=True, skip_errors=False, skip_organized=True, overwrite=False, reorganize=False)
        plan = core.build_plan(plugins, self.db, opts, self.folders)
        if not plan.actions:
            self.set_hint(tr("У этого плагина нет файла пресета, копировать нечего."))
            return
        if self.s["preview"]:
            target = os.path.relpath(plan.actions[0].dest_dir, self.db)
            text = tr("Скопировать: {items}?\n\n{target}").format(items=plugins_word(len(plan.actions)), target=target)
            if Dialog(self.root, self.t, tr("Организовать"), text, [tr("Организовать"), tr("Отмена")]).result != 0:
                return
        if not self._backup_before_change(small=len(plan.actions) == 1):
            return
        result = core.execute(plan, self.db, opts, log=self.s.log.write)
        if result.created_files or result.moved_files or result.new_removed:
            core.write_journal(self.s.journal, self.db, result)
        if result.errors:
            self._show_errors(result.errors)
        self.refresh()

    def _remove_plugins(self, plugins: list[core.Plugin]) -> None:
        """Убирает организованные копии в корзину."""
        names = sorted({p.name for p in plugins if p.organized_in}, key=str.casefold)
        if not names:
            return
        target = plugins[0].organized_in if len(names) == 1 else ""
        message = (tr("Убрать «{name}» из организованных?\n\n{target}\n\n").format(name=names[0], target=target) if len(names) == 1
                   else tr("Убрать из организованных {items}?\n\n").format(items=plugins_word(len(names))))
        message += tr("Файлы копии уйдут в корзину. Исходные плагины и папка Installed не меняются.")
        if self.s["confirm_delete"] and Dialog(self.root, self.t, tr("Убрать копию"), message, [tr("Убрать"), tr("Отмена")]).result != 0:
            return
        if not self._backup_before_change(small=len(names) == 1):
            return
        done = set()
        errors = []
        for p in plugins:
            ident = (p.kind, p.name_id)
            if not p.organized_in or ident in done:
                continue
            done.add(ident)
            try:
                core.remove_organized(p, self.db)
                self.s.log.write("remove", f"{p.name}: {os.path.relpath(p.organized_in, self.db)}")
            except (OSError, ValueError) as exc:
                errors.append((p.name, str(exc)))
        if errors:
            self._show_errors(errors)
        self.refresh()

    def _context_menu(self, event) -> None:
        """Меню по правому клику на строке."""
        selection = self.grid.selection()
        if not selection:
            return
        menu = self._menu()
        missing = [p for p in selection if not p.organized_in and p.fst]
        present = [p for p in selection if p.organized_in]
        one = selection[0]
        if missing:
            menu.add_command(label=tr("Организовать ({count})").format(count=len(missing)), command=lambda: self._copy_plugins(missing))
        if present:
            menu.add_command(label=tr("Убрать копию ({count})").format(count=len(present)), command=lambda: self._remove_plugins(present))
        menu.add_command(label=tr("Изменить вендора…"), command=self._focus_vendor)
        menu.add_cascade(label=tr("Назначение"), menu=self._purpose_popup(menu))
        menu.add_separator()
        if one.organized_in:
            menu.add_command(label=tr("Открыть папку копии"), command=lambda: self._open(one.organized_in))
        if one.primary and os.path.isdir(os.path.dirname(one.primary.filename)):
            menu.add_command(label=tr("Открыть папку плагина"), command=lambda: self._open(os.path.dirname(one.primary.filename)))
        menu.tk_popup(event.x_root, event.y_root)
        menu.grab_release()

    def _focus_vendor(self) -> None:
        """Переходит к полю производителя."""
        self.show_page("plugin")
        self.vendor_entry.focus_set()
        self.vendor_entry.select_range(0, "end")

    def _open(self, path: str) -> None:
        """Открывает папку или адрес средствами Windows."""
        try:
            os.startfile(path)
        except OSError as exc:
            self.set_hint(tr("Не удалось открыть папку: {error}").format(error=exc.strerror))

    # ------------------------------------------------------------------ правка производителя
    def apply_vendor(self) -> None:
        """Применяет введённого производителя."""
        selection = self.grid.selection()
        vendor = self.vendor_var.get().strip()
        if not selection or (not vendor and len(selection) > 1):
            return
        overrides = self.s["vendor_overrides"]
        for p in selection:
            if vendor and vendor != p.raw_vendor:
                overrides[p.name_id] = vendor
            else:
                overrides.pop(p.name_id, None)
        self._after_vendor_edit(selection)

    def reset_vendor(self) -> None:
        """Возвращает производителя из плагина."""
        selection = self.grid.selection()
        for p in selection:
            self.s["vendor_overrides"].pop(p.name_id, None)
        self._after_vendor_edit(selection)

    def _after_vendor_edit(self, selection: list[core.Plugin]) -> None:
        """После правки: при необходимости переносит копии в новые папки."""
        self.s.save()
        self._apply_vendors()
        opts = self._options()
        misplaced = {}
        for p in selection:
            if p.organized_in:
                dest = core.target_folder(self.db, p, opts, self.folders)
                if os.path.normcase(dest) != os.path.normcase(p.organized_in):
                    misplaced[(p.kind, p.name_id)] = (p, dest)
        if misplaced:
            first = next(iter(misplaced.values()))
            text = tr("{items} уже лежат в других папках.\nПереместить в папку нового вендора?\n\n{target}").format(
                items=plugins_word(len(misplaced)), target=first[1])
            if (not self.s["confirm_move"] or Dialog(self.root, self.t, tr("Вендор изменён"), text, [tr("Переместить"), tr("Оставить")]).result == 0) \
                    and self._backup_before_change(small=len(misplaced) == 1):
                errors = []
                for p, dest in misplaced.values():
                    try:
                        core.move_organized(p, dest, self.db)
                        self.s.log.write("move", f"{p.name} -> {os.path.relpath(dest, self.db)}")
                    except (OSError, ValueError) as exc:
                        errors.append((p.name, str(exc)))
                if errors:
                    self._show_errors(errors)
        self.refresh()

    # ------------------------------------------------------------------ раскладка
    def organize_click(self, proposal: bool = False) -> None:
        """Главная кнопка. proposal: предложение при запуске, молчит, если предлагать нечего."""
        if self.backup_running:
            return
        if self.worker:
            self.cancel_flag.set()
            self.main_btn.set_text(tr("Отмена…"))
            return
        if not self.db:
            Dialog(self.root, self.t, tr("База не найдена"), tr("Укажите папку базы плагинов FL Studio."), [tr("Понятно")])
            return
        opts = self._options()
        plan = core.build_plan(self.active_plugins(), self.db, opts, self.folders)
        skipped = "\n".join(tr("Пропущено ({reason}): {count}").format(reason=tr(SKIP_LABELS.get(k, k)), count=v) for k, v in plan.skipped.items())
        if not plan.actions:
            if not proposal:
                Dialog(self.root, self.t, tr("Нечего копировать"), tr("Все выбранные плагины уже организованы.\n\n") + skipped, [tr("Понятно")])
            return
        if self.s["preview"] or proposal or (plan.moves and self.s["confirm_move"]):
            vendors = plan.folders(self.db)
            kind_note = {"Effects": 0, "Generators": 0}
            for a in plan.actions:
                kind_note[a.plugin.kind] += 1
            copies = len(plan.actions) - plan.moves
            header = tr("Будет скопировано: {items} (эффекты: {effects}, синтезаторы: {synths}) в {folders}.\nИсходные файлы не меняются.").format(
                items=plugins_word(copies), effects=kind_note["Effects"], synths=kind_note["Generators"],
                folders=plural(len(vendors), "папку", "папки", "папок"))
            if plan.moves:
                header += "\n" + tr("Будет перемещено: {items}.").format(items=plugins_word(plan.moves))
            if opts.move_from_new:
                from_new = sum(1 for a in plan.actions if core.new_entries(a.plugin, self.db))
                if from_new:
                    header += "\n" + tr("Из списка New уйдёт: {items}.").format(items=plugins_word(from_new))
            if self.s["auto_backup"]:
                header += "\n" + tr("Перед началом будет создан бэкап базы.")
            if skipped:
                header += "\n\n" + skipped
            dialog = Dialog(self.root, self.t, tr("Предпросмотр"), header, [tr("Организовать"), tr("Отмена")],
                            rows=[(name, str(count)) for name, count in vendors.items()], width=520)
            if dialog.result != 0:
                return
        self.cancel_flag.clear()
        self.main_btn.set_text(tr("Отмена"))
        self.worker = threading.Thread(target=self._run, args=(plan, opts), daemon=True)
        self.worker.start()
        self.root.after(50, self._poll)

    def _run(self, plan: core.Plan, opts: core.Options) -> None:
        """Работа фонового потока раскладки."""
        def progress(done, total, name):
            """Передаёт прогресс в главный поток."""
            self.events.put(("progress", done, total, name))

        try:
            if self.s["auto_backup"]:
                self.events.put(("progress", 0, len(plan.actions), tr("бэкап базы")))
                self.s.log.write("backup", core.backup_database(self.db, self.s.backups, self.s["backup_keep"]))
                self.last_backup = time.time()
            result = core.execute(plan, self.db, opts, progress, self.cancel_flag.is_set, self.s.log.write)
            self.events.put(("done", result))
        except Exception as exc:  # окно не должно зависнуть в состоянии работы
            self.events.put(("failed", str(exc)))

    def _poll(self) -> None:
        """Главный поток забирает события фоновой работы."""
        latest = None
        finished = None
        try:
            while True:
                event = self.events.get_nowait()
                if event[0] == "progress":
                    latest = event
                else:
                    finished = event
        except queue.Empty:
            pass
        if latest:
            _, done, total, name = latest
            self.set_hint(tr("Копирование {done} из {total}: {name}").format(done=done, total=total, name=name))
        if finished:
            self._finish(finished)
        else:
            self.root.after(50, self._poll)

    def _finish(self, event) -> None:
        """Показывает итог раскладки."""
        self.worker = None
        self.main_btn.set_text(tr("Организовать плагины"))
        self.hint_text = ""
        if event[0] == "failed":
            Dialog(self.root, self.t, tr("Ошибка"), event[1], [tr("Понятно")])
            self.refresh()
            return
        result: core.RunResult = event[1]
        if result.created_files or result.moved_files or result.new_removed:
            core.write_journal(self.s.journal, self.db, result)
        self.refresh()
        lines = [tr("Скопировано: {items}.").format(items=plugins_word(result.copied))]
        if result.moved:
            lines.append(tr("Перемещено: {items}.").format(items=plugins_word(result.moved)))
        if result.skipped_existing:
            lines.append(tr("Файл уже был на месте: {count}.").format(count=result.skipped_existing))
        if result.cancelled:
            lines.insert(0, tr("Остановлено по вашей команде."))
        if result.created_files or result.moved_files:
            lines.append(tr("\nКопирование можно отменить кнопкой «Отменить» на вкладке «Настройки».\nЕсли FL Studio открыт, обновите браузер плагинов."))
        rows = None
        if result.errors:
            lines.append(tr("\nНе удалось скопировать: {count}.").format(count=len(result.errors)))
            if any("denied" in e[1].lower() or "отказ" in e[1].lower() for e in result.errors):
                lines.append(tr("Нет прав на запись в эту папку: запустите программу от имени администратора."))
            rows = [(name, reason) for name, reason in result.errors[:200]]
        Dialog(self.root, self.t, tr("Готово"), "\n".join(lines), [tr("Понятно")], rows=rows, width=520)

    def _show_errors(self, errors: list[tuple[str, str]]) -> None:
        """Окно со списком ошибок."""
        Dialog(self.root, self.t, tr("Ошибки"), tr("Не выполнено: {count}.").format(count=len(errors)), [tr("Понятно")], rows=errors[:200], width=520)

    def undo_click(self) -> None:
        """Кнопка «Отменить»."""
        journal = core.read_journal(self.s.journal)
        if not journal or self.worker:
            return
        count = len(journal.get("files", [])) + len(journal.get("moved", [])) + len(journal.get("new_removed", []))
        message = tr("Убрать файлы последнего копирования ({count})?\n\nОни уйдут в корзину. Файлы, изменённые после копирования, останутся на месте.").format(count=count)
        if self.s["confirm_delete"] and Dialog(self.root, self.t, tr("Отменить копирование"), message, [tr("Отменить копирование"), tr("Закрыть")]).result != 0:
            return
        if not self._backup_before_change():
            return
        try:
            removed, kept = core.undo(self.s.journal, self.db)
            self.s.log.write("undo", f"{removed} / {kept}")
            note = tr("Убрано файлов: {removed}.").format(removed=removed) + (tr(" Оставлено без изменений: {kept}.").format(kept=kept) if kept else "")
            self.set_hint(note)
            self.root.after(6000, lambda: self.set_hint(""))
        except OSError as exc:
            Dialog(self.root, self.t, tr("Ошибка"), str(exc), [tr("Понятно")])
        self.refresh()

    def _update_undo_button(self) -> None:
        """Кнопка активна, только если есть что отменять."""
        if self.undo_btn:
            available = core.read_journal(self.s.journal)
            self.undo_btn.set_enabled(bool(available) and os.path.normcase(available.get("db", "")) == os.path.normcase(self.db))

    # ------------------------------------------------------------------ папки
    def choose_database(self) -> None:
        """Выбор папки базы вручную."""
        folder = filedialog.askdirectory(parent=self.root, title=tr("Папка Plugin database"), initialdir=self.db or None, mustexist=True)
        if not folder:
            return
        folder = os.path.normpath(folder)
        for candidate in (folder, os.path.join(folder, core._DB_SUBPATH), os.path.join(folder, "Presets", "Plugin database"),
                          os.path.join(folder, "Plugin database")):
            if core.is_database(candidate):
                self.db = candidate
                self.s["db"] = candidate
                self.s.save()
                self._update_db_label()
                self.refresh()
                return
        Dialog(self.root, self.t, tr("Папка не подходит"),
               tr("В этой папке нет подпапки Installed. Выберите папку Plugin database: обычно это Image-Line\\FL Studio\\Presets\\Plugin database."), [tr("Понятно")])

    def add_custom_source(self) -> None:
        """Добавляет свою папку с плагинами."""
        folder = filedialog.askdirectory(parent=self.root, title=tr("Папка с файлами .fst и .nfo"), mustexist=True)
        if folder:
            folder = os.path.normpath(folder)
            if folder not in self.s["custom_sources"]:
                self.s["custom_sources"].append(folder)
                self.s.save()
                self.selected_source = "custom:" + os.path.normcase(folder)
                self.refresh()

    def remove_custom_source(self) -> None:
        """Убирает свою папку из списка."""
        source = next((s for s in self.sources if s.id == self.selected_source and s.custom), None)
        if source is None:
            self.set_hint(tr("Выберите в списке свою папку: встроенные источники убрать нельзя."))
            return
        self.s["custom_sources"] = [f for f in self.s["custom_sources"] if "custom:" + os.path.normcase(os.path.normpath(f)) != source.id]
        self.s.save()
        self.selected_source = None
        self.refresh()

    # ------------------------------------------------------------------ обновления
    def check_updates(self) -> None:
        """Единственное обращение программы к сети, только по этой кнопке."""
        box: dict = {}

        def fetch():
            """Запрос в фоновом потоке."""
            try:
                box["tag"] = core.latest_release(PROJECT_REPO)
            except OSError as exc:
                box["error"] = str(exc)

        def wait():
            """Ждёт ответа и показывает результат."""
            if thread.is_alive():
                self.root.after(150, wait)
                return
            self.set_hint("")
            tag = box.get("tag")
            if tag is None:
                Dialog(self.root, self.t, tr("Обновления"), tr("Не удалось проверить обновления: нет связи с GitHub или релизов пока нет."), [tr("Понятно")])
            elif core.version_tuple(tag) > core.version_tuple(VERSION):
                text = tr("Доступна версия {version}. Открыть страницу загрузки?").format(version=tag.lstrip("v"))
                if Dialog(self.root, self.t, tr("Обновления"), text, [tr("Открыть"), tr("Закрыть")]).result == 0:
                    self._open(PROJECT_URL + "/releases/latest")
            else:
                Dialog(self.root, self.t, tr("Обновления"), tr("Установлена последняя версия."), [tr("Понятно")])

        self.set_hint(tr("Проверка обновлений…"))
        thread = threading.Thread(target=fetch, daemon=True)
        thread.start()
        wait()

    # ------------------------------------------------------------------ поведение окна
    def _apply_topmost(self) -> None:
        """Поверх всех окон."""
        self.root.attributes("-topmost", bool(self.s["always_on_top"]))

    def minimize(self) -> None:
        """Сворачивает окно."""
        user32.ShowWindow(hwnd_of(self.root), 6)

    def toggle_maximize(self) -> None:
        """Разворачивает или возвращает окно."""
        if self.maximized:
            self.root.geometry(self.normal_geometry)
            self.maximized = False
        else:
            self.normal_geometry = self.root.geometry()
            x, y, w, h = work_area(self.root)
            self.root.geometry(f"{w}x{h}+{x}+{y}")
            self.maximized = True

    def _edge_at(self, event) -> str:
        """Какой край окна под мышью."""
        grip = self.t.p(6)
        w, h = self.frame.winfo_width(), self.frame.winfo_height()
        edge = ""
        if event.y >= h - grip:
            edge += "s"
        if event.x <= grip:
            edge += "w"
        elif event.x >= w - grip:
            edge += "e"
        return edge

    def _edge_motion(self, event) -> None:
        """Курсор изменения размера у края."""
        cursors = {"s": "sb_v_double_arrow", "e": "sb_h_double_arrow", "w": "sb_h_double_arrow",
                   "se": "size_nw_se", "sw": "size_ne_sw"}
        self.frame.configure(cursor=cursors.get(self._edge_at(event), "") if not self.maximized else "")

    def _edge_press(self, event) -> None:
        """Начало изменения размера."""
        edge = self._edge_at(event)
        if edge and not self.maximized:
            r = self.root
            self.resize_state = (edge, event.x_root, event.y_root, r.winfo_x(), r.winfo_y(), r.winfo_width(), r.winfo_height())

    def _edge_drag(self, event) -> None:
        """Меняет размер окна."""
        if not self.resize_state:
            return
        edge, x0, y0, wx, wy, ww, wh = self.resize_state
        p = self.t.p
        min_w, min_h = p(900), p(679)
        dx, dy = event.x_root - x0, event.y_root - y0
        x, y, w, h = wx, wy, ww, wh
        if "e" in edge:
            w = max(min_w, ww + dx)
        if "w" in edge:
            w = max(min_w, ww - dx)
            x = wx + ww - w
        if "s" in edge:
            h = max(min_h, wh + dy)
        self.root.geometry(f"{w}x{h}+{x}+{y}")

    def _edge_release(self) -> None:
        """Конец изменения размера."""
        self.resize_state = None

    def _save_layout(self) -> None:
        """Запоминает окно, колонки, поиск, вкладку и выбор."""
        scale = self.t.scale
        self.s["left_width"] = round(self.left_w / scale)
        self.s["column_widths"] = {k: round(v / scale) for k, v in self.grid.widths.items()}
        self.s["sort"] = [self.grid.sort_key, self.grid.sort_reverse]
        self.s["column_order"] = self.grid.order[1:]
        self.s["geometry"] = self.normal_geometry if self.maximized else self.root.geometry()
        self.s["find_text"] = self.find_var.get()
        self.s["main_tab"] = self.main_tab
        self.s["side_page"] = self.page
        self.s["selected"] = sorted(self.grid.selected)[:200]

    def close(self) -> None:
        """Кнопка закрытия: выход или трей, смотря по настройке."""
        if self.s["close_action"] == "tray" and self._to_tray():
            return
        self.quit()

    def _to_tray(self) -> bool:
        """Прячет окно в трей. False, если значок создать не удалось."""
        if self.tray is None:
            import tray
            self.tray = tray.Tray(resource_path("assets", "app.ico"), APP_TITLE, lambda: self.root.after(0, self.restore_window),
                                  lambda: self.root.after(0, self._tray_menu))
        if not self.tray.show():
            return False
        self._save_layout()
        self.s.save()
        self.about.hide()
        self.root.withdraw()
        return True

    def _tray_menu(self) -> None:
        """Меню значка в трее."""
        menu = self._menu()
        menu.add_command(label=tr("Открыть"), command=self.restore_window)
        menu.add_command(label=tr("Выход"), command=self.quit)
        menu.tk_popup(self.root.winfo_pointerx(), self.root.winfo_pointery())
        menu.grab_release()

    def quit(self) -> None:
        """Выход из программы."""
        if self.tray:
            self.tray.hide()
        if self.worker:
            self.cancel_flag.set()
            self.worker.join(timeout=5)
        self._save_layout()
        self.s.save()
        self.root.destroy()


def resource_path(*parts: str) -> str:
    """Путь к файлу внутри сборки или проекта."""
    base = getattr(sys, "_MEIPASS", None) or core.app_dir()
    return os.path.join(base, *parts)


def create_window(settings: core.Settings, db_override: str | None = None, forced_theme: str | None = None, show_event=None) -> tuple[tk.Tk, App]:
    """Создаёт окно и настраивает его положение."""
    scale = enable_dpi_awareness()
    root = tk.Tk()
    root.withdraw()
    root.title(APP_TITLE)
    icon = resource_path("assets", "app.ico")
    if os.path.isfile(icon):
        try:
            root.iconbitmap(default=icon)
        except tk.TclError:
            pass
    app = App(root, scale, settings, db_override, forced_theme, show_event)
    theme = app.t
    geometry = settings["geometry"]
    if not geometry or not _geometry_visible(root, geometry):
        p = theme.p
        w, h = p(1236), p(679)
        sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
        w, h = min(w, sw), min(h, sh - p(48))
        geometry = f"{w}x{h}+{(sw - w) // 2}+{max(0, (sh - h) // 2 - p(20))}"
    root.geometry(geometry)
    root.overrideredirect(True)
    root.update_idletasks()
    make_app_window(root)
    if settings["always_on_top"]:
        root.attributes("-topmost", True)
    root.deiconify()
    root.lift()
    root.focus_force()
    return root, app


def _geometry_visible(root: tk.Misc, geometry: str) -> bool:
    """Видно ли сохранённое положение окна на текущих мониторах."""
    try:
        size, x, y = geometry.replace("-", "+-").split("+")[:3]
        x, y = int(x), int(y)
    except ValueError:
        return False
    vx, vy = root.winfo_vrootx(), root.winfo_vrooty()
    vw, vh = user32.GetSystemMetrics(78), user32.GetSystemMetrics(79)
    return vx - 40 <= x < vx + vw - 40 and vy - 10 <= y < vy + vh - 40


def run(settings: core.Settings, db_override: str | None = None, forced_theme: str | None = None, show_event=None) -> None:
    """Запускает программу."""
    root, app = create_window(settings, db_override, forced_theme, show_event)
    fade_in_window(root, app.motion, 180)
    root.after(220, app.startup)
    root.mainloop()
