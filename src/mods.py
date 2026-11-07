"""Моды: необязательные дополнения к программе.

Все моды лежат в папке Mods рядом с папкой Backups, каждый в своей папке с тем же именем, что и у мода.
В папке мода есть index.json с описанием, а рядом все его файлы и папки. Код начинается с файла из поля
entry (обычно mod.py), в нём нужна функция activate(api). Первые моды идут в сборке и при первом
включении копируются в папку Mods. Дальше ими можно распоряжаться как обычными папками.
Ошибка в моде не должна ломать программу: она записывается в карточку мода, а его обработчик отключается.
"""
from __future__ import annotations

import ctypes
import importlib.util
import json
import os
import re
import shutil
import sys
from dataclasses import dataclass, field

import core
import i18n
import rules

MANIFEST = "index.json"
ENTRY = "mod.py"  # файл кода, если в index.json не указан другой


@dataclass(slots=True)
class ModInfo:
    """Описание мода из его mod.json."""
    id: str
    name: str
    type: str
    version: str
    author: str
    description: dict
    folder: str
    entry: str = ENTRY
    error: str = ""
    actions: list = field(default_factory=list)

    @property
    def text(self) -> str:
        """Описание на языке интерфейса, иначе на английском."""
        return self.description.get(i18n.LANG) or self.description.get("EN-en") or ""


def bundled_folder() -> str:
    """Папка встроенных модов: внутри сборки или в проекте."""
    return os.path.join(getattr(sys, "_MEIPASS", None) or core.app_dir(), "mods")


def user_folder(base: str | None = None) -> str:
    """Папка Mods там же, где Backups. base: папка данных программы."""
    return os.path.join(base or core.data_dir(), "Mods")


def install_bundled(base: str | None = None) -> None:
    """Первое включение: копирует моды из сборки в папку Mods. Удалённый потом мод не вернётся."""
    source, target = bundled_folder(), user_folder(base)
    if not os.path.isdir(target) and os.path.isdir(source):
        shutil.copytree(source, target, ignore=shutil.ignore_patterns("__pycache__"))


def read_manifest(folder: str) -> ModInfo | None:
    """Читает index.json. id мода это имя его папки. None, если файла нет или он испорчен."""
    try:
        with open(os.path.join(folder, MANIFEST), encoding="utf-8") as f:
            raw = json.load(f)
        return ModInfo(os.path.basename(folder), str(raw["name"]), str(raw.get("type", "")), str(raw.get("version", "")),
                       str(raw.get("author", "")), dict(raw.get("description", {})), folder, str(raw.get("entry", ENTRY)))
    except (OSError, ValueError, KeyError, TypeError):
        return None


def discover(base: str | None = None) -> list[ModInfo]:
    """Все моды из папки Mods. Если туда нельзя было записать, моды из сборки."""
    root = user_folder(base) if os.path.isdir(user_folder(base)) else bundled_folder()
    if not os.path.isdir(root):
        return []
    found = (read_manifest(os.path.join(root, name)) for name in sorted(os.listdir(root), key=str.casefold))
    return [info for info in found if info]


class Api:
    """То, чем мод может пользоваться. Передаётся в activate(api)."""

    def __init__(self, manager: "Manager", info: ModInfo):
        self.manager, self.info = manager, info
        self.app = manager.app
        self.folder = info.folder

    def add_purpose(self, purpose_id: str, labels: dict) -> None:
        """Новое назначение. labels: подписи по кодам языков, обязателен EN-en."""
        rules.add_purpose(purpose_id, labels)
        self.manager.purposes.append(purpose_id)

    def add_purpose_hook(self, function, priority: int = 50) -> None:
        """function(plugin) возвращает список назначений или None. Меньший priority спрашивается раньше."""
        self.manager.add_hook("purpose", self.info, function, priority)

    def add_vendor_hook(self, function) -> None:
        """function(plugin) возвращает производителя, когда его не указал сам плагин."""
        self.manager.add_hook("vendor", self.info, function)

    def add_search_hook(self, function) -> None:
        """function(plugin) возвращает слова, по которым плагин находится в поиске."""
        self.manager.add_hook("search", self.info, function)

    def on_purpose_changed(self, function) -> None:
        """function(plugins, purpose): пользователь назначил плагинам назначение вручную."""
        self.manager.add_hook("purpose_changed", self.info, function)

    def on_load(self, function) -> None:
        """function(plugins) после чтения базы. True значит, что назначения надо пересчитать."""
        self.manager.add_hook("load", self.info, function)

    def set_preview(self, function) -> None:
        """function(plan, header) заменяет окно предпросмотра. True: организовать, False: отмена."""
        self.manager.add_hook("preview", self.info, function)

    def set_row_marker(self, function) -> None:
        """function(plugin) возвращает цвет полоски у строки списка или None."""
        self.manager.add_hook("marker", self.info, function)

    def add_action(self, label: dict, function) -> None:
        """Кнопка на карточке мода. label: подписи по кодам языков."""
        self.info.actions.append((label, function))

    @staticmethod
    def text(labels: dict) -> str:
        """Текст на языке интерфейса, иначе на английском."""
        return labels.get(i18n.LANG) or labels.get("EN-en") or ""

    def read_json(self, name: str, default=None):
        """Читает JSON из папки мода."""
        return self._read(os.path.join(self.folder, name), default)

    def data_path(self) -> str:
        """Файл данных мода рядом с настройками программы. Папку мода менять нельзя: в сборке она временная."""
        folder = os.path.join(self.app.s.folder, "ModData")
        os.makedirs(folder, exist_ok=True)
        return os.path.join(folder, self.info.id + ".json")

    def load_data(self, default=None):
        """Читает данные мода."""
        return self._read(self.data_path(), default)

    def save_data(self, data) -> None:
        """Сохраняет данные мода."""
        core._write_json(self.data_path(), data)

    @staticmethod
    def _read(path: str, default):
        """Читает JSON; при ошибке возвращает default."""
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError):
            return default

    @staticmethod
    def download(url: str, path: str) -> bool:
        """Скачивает файл средствами Windows. Вызывайте только по действию пользователя."""
        return ctypes.windll.urlmon.URLDownloadToFileW(None, url, path, 0, None) == 0


class Manager:
    """Включает моды и вызывает их обработчики."""

    def __init__(self, app):
        self.app = app
        self.mods: list[ModInfo] = []
        self.hooks: dict[str, list] = {}
        self.purposes: list[str] = []

    def add_hook(self, name: str, info: ModInfo, function, priority: int = 50) -> None:
        """Запоминает обработчик."""
        self.hooks.setdefault(name, []).append((priority, info, function))
        self.hooks[name].sort(key=lambda hook: hook[0])

    def reload(self) -> None:
        """Заново находит моды и включает выбранные."""
        for purpose_id in self.purposes:
            rules.remove_purpose(purpose_id)
        self.purposes = []
        self.hooks = {}
        self.mods = []
        settings = self.app.s
        if not settings["mods_enabled"]:
            return
        try:
            install_bundled(settings.folder)
        except OSError:
            pass  # в папку нельзя записать: моды будут работать прямо из сборки
        self.mods = discover(settings.folder)
        for info in self.mods:
            if info.id in settings["mods_active"]:
                self._activate(info)

    def _activate(self, info: ModInfo) -> None:
        """Запускает код одного мода. Ошибка остаётся в его карточке."""
        path = os.path.join(info.folder, info.entry)
        if not os.path.exists(path):
            return
        try:
            spec = importlib.util.spec_from_file_location("fodb_mod_" + re.sub(r"\W", "_", info.id), path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            module.activate(Api(self, info))
        except Exception as exc:  # чужой код может упасть как угодно
            info.error = f"{type(exc).__name__}: {exc}"

    def _call(self, name: str, *args):
        """Вызывает обработчики по очереди и отдаёт ответы. Упавший обработчик отключается."""
        for hook in list(self.hooks.get(name, ())):
            try:
                yield hook[2](*args)
            except Exception as exc:
                hook[1].error = f"{type(exc).__name__}: {exc}"
                self.hooks[name].remove(hook)

    def purpose_hooks(self) -> list:
        """Обработчики для rules.classify. Каждый защищён от ошибок мода."""
        return [lambda plugin: next((answer for answer in self._call("purpose", plugin) if answer), None)] if self.hooks.get("purpose") else []

    def vendor(self, plugin) -> str:
        """Производитель из модов, если он нашёлся."""
        return next((answer for answer in self._call("vendor", plugin) if answer), "")

    def search(self, plugin) -> str:
        """Дополнительные слова для поиска."""
        return " ".join(answer for answer in self._call("search", plugin) if answer)

    def purpose_changed(self, plugins: list, purpose: str | None) -> None:
        """Сообщает модам о ручном назначении."""
        for _answer in self._call("purpose_changed", plugins, purpose):
            pass

    def after_load(self, plugins: list) -> bool:
        """После чтения базы. True, если какой-то мод просит пересчитать назначения."""
        return any([answer for answer in self._call("load", plugins)])

    def preview(self, plan, header: str) -> bool | None:
        """Окно предпросмотра из мода. None, если такого мода нет."""
        return next(self._call("preview", plan, header), None)

    def marker(self, plugin) -> str | None:
        """Цвет полоски у строки списка."""
        return next((answer for answer in self._call("marker", plugin) if answer), None)
