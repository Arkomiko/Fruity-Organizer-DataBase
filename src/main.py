"""Точка входа Fruity Organizer DataBase.

Необязательные аргументы: --db ПУТЬ, --settings ПАПКА, --lang ru|en, --theme ФАЙЛ.flstheme
"""
import argparse
import ctypes
from ctypes import wintypes

import core
import i18n

_INSTANCE = "FODB.SingleWindow"
_ALREADY_EXISTS = 183


def single_instance():
    """Разрешает одно окно: второй запуск будит первый и выходит. Возвращает событие пробуждения или None."""
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateMutexW.restype = wintypes.HANDLE
    kernel32.CreateMutexW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR]
    kernel32.CreateEventW.restype = wintypes.HANDLE
    kernel32.CreateEventW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.BOOL, wintypes.LPCWSTR]
    kernel32.SetEvent.argtypes = [wintypes.HANDLE]
    kernel32.CreateMutexW(None, False, _INSTANCE)
    first = ctypes.get_last_error() != _ALREADY_EXISTS
    event = kernel32.CreateEventW(None, False, False, _INSTANCE + ".Show")
    if first:
        return event
    kernel32.SetEvent(event)
    return None


def main() -> None:
    """Разбирает аргументы, загружает настройки и открывает окно."""
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--db")
    parser.add_argument("--settings")
    parser.add_argument("--lang")
    parser.add_argument("--theme")
    args, _ = parser.parse_known_args()
    show_event = single_instance()
    if show_event is None:
        return
    settings = core.Settings(args.settings)
    i18n.set_language(args.lang or settings["language"])
    import ui
    ui.run(settings, args.db, args.theme, show_event)


if __name__ == "__main__":
    main()
