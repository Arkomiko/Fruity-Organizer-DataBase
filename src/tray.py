"""Значок в области уведомлений. Сообщения Windows обрабатывает цикл событий Tk, свой цикл не нужен."""
from __future__ import annotations

import ctypes
from ctypes import wintypes

_CALLBACK = 0x8000 + 41  # диапазон WM_APP
_WM_LBUTTONUP, _WM_RBUTTONUP = 0x0202, 0x0205
_WNDPROC = ctypes.WINFUNCTYPE(ctypes.c_ssize_t, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
shell32 = ctypes.windll.shell32
user32.DefWindowProcW.restype = ctypes.c_ssize_t
user32.DefWindowProcW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.CreateWindowExW.restype = wintypes.HWND
user32.CreateWindowExW.argtypes = [wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                   wintypes.HWND, wintypes.HMENU, wintypes.HINSTANCE, wintypes.LPVOID]
user32.LoadImageW.restype = wintypes.HANDLE
user32.LoadImageW.argtypes = [wintypes.HINSTANCE, wintypes.LPCWSTR, wintypes.UINT, ctypes.c_int, ctypes.c_int, wintypes.UINT]
kernel32.GetModuleHandleW.restype = wintypes.HMODULE
kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]


class _Class(ctypes.Structure):
    """Структура Windows WNDCLASS."""
    _fields_ = [("style", wintypes.UINT), ("proc", _WNDPROC), ("extra", ctypes.c_int), ("window_extra", ctypes.c_int), ("instance", wintypes.HINSTANCE),
                ("icon", wintypes.HANDLE), ("cursor", wintypes.HANDLE), ("background", wintypes.HANDLE), ("menu", wintypes.LPCWSTR), ("name", wintypes.LPCWSTR)]


class _Icon(ctypes.Structure):
    """Структура Windows NOTIFYICONDATA."""
    _fields_ = [("size", wintypes.DWORD), ("window", wintypes.HWND), ("id", wintypes.UINT), ("flags", wintypes.UINT), ("message", wintypes.UINT),
                ("icon", wintypes.HANDLE), ("tip", wintypes.WCHAR * 128)]


class Tray:
    """Значок в трее: левый клик открывает окно, правый показывает меню."""

    def __init__(self, icon_path: str, tip: str, on_open, on_menu):
        """Создаёт скрытое окно для сообщений и загружает значок."""
        self.on_open, self.on_menu = on_open, on_menu
        self._proc = _WNDPROC(self._message)  # держим ссылку: Windows вызывает функцию, пока живо окно
        instance = kernel32.GetModuleHandleW(None)
        window_class = _Class(proc=self._proc, instance=instance, name="FODBTray")
        user32.RegisterClassW(ctypes.byref(window_class))
        self.window = user32.CreateWindowExW(0, "FODBTray", None, 0, 0, 0, 0, 0, None, None, instance, None)
        icon = user32.LoadImageW(None, icon_path, 1, 16, 16, 0x10) or user32.LoadImageW(None, ctypes.cast(32512, wintypes.LPCWSTR), 1, 16, 16, 0x8000)
        self.data = _Icon(size=ctypes.sizeof(_Icon), window=self.window, id=1, flags=0x1 | 0x2 | 0x4, message=_CALLBACK, icon=icon, tip=tip[:127])
        self.shown = False

    def _message(self, window, message, wparam, lparam):
        """Получает клики по значку от Windows."""
        if message == _CALLBACK:
            if lparam == _WM_LBUTTONUP:
                self.on_open()
            elif lparam == _WM_RBUTTONUP:
                self.on_menu()
            return 0
        return user32.DefWindowProcW(window, message, wparam, lparam)

    def show(self) -> bool:
        """Показывает значок. True, если получилось."""
        if not self.shown:
            self.shown = bool(shell32.Shell_NotifyIconW(0, ctypes.byref(self.data)))
        return self.shown

    def hide(self) -> None:
        """Убирает значок."""
        if self.shown:
            shell32.Shell_NotifyIconW(2, ctypes.byref(self.data))
            self.shown = False
