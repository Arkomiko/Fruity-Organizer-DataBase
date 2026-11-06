"""Логика базы плагинов: чтение индекса, план раскладки и его выполнение.

Здесь нет кода интерфейса, поэтому всё можно проверить тестами на временной копии базы.
"""
from __future__ import annotations

import base64
import ctypes
import json
import os
import re
import shutil
import struct
import sys
import tempfile
import time
import zipfile
from ctypes import wintypes
from dataclasses import dataclass, field

import rules
from i18n import tr

KINDS = ("Effects", "Generators")
FORMAT_ORDER = ("VST3", "CLAP", "VST", "FL")
FORMAT_PRIORITY = {name: rank for rank, name in enumerate(FORMAT_ORDER)}
UNKNOWN_VENDOR = "Unknown"
INDEX_FILE = ".Plugins.ini"
_DB_SUBPATH = os.path.join("FL Studio", "Presets", "Plugin database")
_FORBIDDEN = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_RESERVED = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}


# --------------------------------------------------------------------------------------------
# Модель данных
# --------------------------------------------------------------------------------------------
@dataclass(slots=True)
class PluginFile:
    """Один файл плагина (у плагина их может быть несколько)."""
    name: str
    filename: str
    format: str
    bits: str
    vendor: str
    category: str


@dataclass(slots=True)
class Plugin:
    """Запись о плагине из папки Installed."""
    key: str  # путь от корня источника без расширения, уникален в списке
    kind: str  # Effects или Generators
    group: str  # папка источника: VST3, VST, CLAP, Fruity, New или своя
    source: str  # id строки источника
    name: str
    files: list[PluginFile]
    ok: bool
    type_known: bool
    fst: str | None
    nfo: str | None
    fst_vendor: str = ""
    installed: float = 0.0  # дата файла (Unix-время), 0 если неизвестна
    size: int = 0
    # заполняет приложение
    vendor: str = ""
    vendor_edited: bool = False
    purposes: list = field(default_factory=list)
    purpose_source: str = ""
    organized_in: str | None = None
    search: str = ""

    @property
    def name_id(self) -> str:
        """Имя файла пресета в нижнем регистре: именно оно совпадает на диске у копий плагина."""
        stem = os.path.splitext(os.path.basename(self.fst))[0] if self.fst else self.name
        return stem.casefold()

    @property
    def primary(self) -> PluginFile | None:
        """Главный файл плагина."""
        return self.files[0] if self.files else None

    @property
    def raw_vendor(self) -> str:
        """Производитель, как его записал плагин."""
        for f in self.files:
            if f.vendor:
                return f.vendor
        return self.fst_vendor

    @property
    def formats(self) -> str:
        """Форматы через плюс, например VST3 + VST."""
        return " + ".join(dict.fromkeys(f.format for f in self.files if f.format))

    @property
    def bits(self) -> str:
        """Разрядность через плюс."""
        return " + ".join(dict.fromkeys(f.bits for f in self.files if f.bits))

    @property
    def filename(self) -> str:
        """Имя главного файла без пути."""
        return os.path.basename(self.files[0].filename) if self.files else ""

    @property
    def directory(self) -> str:
        """Папка главного файла."""
        return os.path.dirname(self.files[0].filename) + "\\" if self.files else ""

    @property
    def category(self) -> str:
        """Категория, заявленная плагином."""
        return next((f.category for f in self.files if f.category), "")


@dataclass(slots=True)
class Source:
    """Строка списка источников: папка, откуда берутся плагины."""
    id: str
    label: str
    path: str
    kind: str | None
    custom: bool = False
    count: int = 0


@dataclass(slots=True)
class Options:
    """Параметры одного запуска раскладки."""
    one_copy: bool = True
    skip_errors: bool = True
    skip_organized: bool = True
    overwrite: bool = False
    reorganize: bool = False
    layout: str = "{vendor}"
    generators_layout: str = ""  # пусто: как у эффектов
    format_order: tuple = FORMAT_ORDER
    folder_language: str = ""  # пусто: язык интерфейса
    strip_suffix: bool = False
    move_from_new: bool = False


@dataclass(slots=True)
class Action:
    """Один шаг плана: куда положить плагин."""
    plugin: Plugin
    dest_dir: str
    move_from: str | None = None  # задано, если копия перемещается, а не создаётся


@dataclass(slots=True)
class Plan:
    """Что будет сделано и что пропущено (с причинами)."""
    actions: list[Action] = field(default_factory=list)
    skipped: dict[str, int] = field(default_factory=dict)

    def skip(self, reason: str) -> None:
        """Считает пропуск по причине."""
        self.skipped[reason] = self.skipped.get(reason, 0) + 1

    @property
    def moves(self) -> int:
        """Сколько шагов перемещают копию, а не создают новую."""
        return sum(1 for a in self.actions if a.move_from)

    def folders(self, db: str) -> dict[str, int]:
        """Сколько плагинов попадёт в каждую папку (пути относительно базы)."""
        result: dict[str, int] = {}
        for a in self.actions:
            label = os.path.relpath(a.dest_dir, db)
            result[label] = result.get(label, 0) + 1
        return dict(sorted(result.items(), key=lambda kv: kv[0].casefold()))


@dataclass(slots=True)
class RunResult:
    """Итог запуска. Списки файлов нужны для отмены."""
    copied: int = 0
    moved: int = 0
    skipped_existing: int = 0
    cancelled: bool = False
    errors: list[tuple[str, str]] = field(default_factory=list)
    created_files: list[dict] = field(default_factory=list)
    created_dirs: list[str] = field(default_factory=list)
    moved_files: list[dict] = field(default_factory=list)
    new_removed: list[dict] = field(default_factory=list)


# --------------------------------------------------------------------------------------------
# Поиск FL Studio
# --------------------------------------------------------------------------------------------
def _registry_paths() -> dict[str, str]:
    """Пути Image-Line из реестра Windows."""
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Image-Line\Shared\Paths") as key:
            values = {}
            i = 0
            while True:
                try:
                    name, value, _ = winreg.EnumValue(key, i)
                except OSError:
                    return values
                values[name] = value
                i += 1
    except (OSError, ImportError):
        return {}


def is_database(path: str) -> bool:
    """Похожа ли папка на базу плагинов (внутри есть Installed)."""
    return bool(path) and os.path.isdir(os.path.join(path, "Installed"))


def find_database() -> tuple[str, str]:
    """Находит базу и папку установки FL Studio. Любой из путей может быть пустым."""
    reg = _registry_paths()
    home = os.path.expanduser("~")
    roots = [reg.get("Shared data", ""),
             os.path.join(home, "Documents", "Image-Line"),
             os.path.join(home, "OneDrive", "Documents", "Image-Line")]
    install = reg.get("Install path", "")
    for root in roots:
        candidate = os.path.join(root, _DB_SUBPATH) if root else ""
        if is_database(candidate):
            return os.path.normpath(candidate), install
    return "", install


# --------------------------------------------------------------------------------------------
# Разбор файлов
# --------------------------------------------------------------------------------------------
def _read_text(path: str) -> str:
    """Читает текстовый файл FL (UTF-8, возможно с BOM)."""
    with open(path, "rb") as f:
        return f.read().decode("utf-8-sig", "replace")


def parse_index(text: str) -> dict[str, dict[str, str]]:
    """Разбирает .Plugins.ini: секция [относительный\\путь] и строки ключ=значение на плагин."""
    sections: dict[str, dict[str, str]] = {}
    current: dict[str, str] | None = None
    for line in text.splitlines():
        if line[:1] == "[" and line[-1:] == "]":
            current = sections.setdefault(line[1:-1], {})
        elif current is not None:
            k, sep, v = line.partition("=")
            if sep:
                current[k] = v
    return sections


def parse_nfo(text: str) -> dict[str, str]:
    """Разбирает .nfo: строки ключ=значение."""
    result = {}
    for line in text.splitlines():
        k, sep, v = line.partition("=")
        if sep:
            result[k] = v
    return result


def read_fst_vendor(path: str) -> str:
    """Читает производителя из конца .fst, не загружая весь файл."""
    try:
        with open(path, "rb") as f:
            f.seek(0, os.SEEK_END)
            f.seek(max(0, f.tell() - 512))
            data = f.read()
    except OSError:
        return ""
    index = data.rfind(b"\x00" * 7)
    if index < 0:
        return ""
    vendor = data[index + 7:].decode("utf-8", "replace").strip("\x00 \r\n\t")
    return vendor if vendor and vendor.isprintable() and "�" not in vendor else ""


def _file_format(filename: str, group: str) -> str:
    """Определяет формат плагина по пути файла."""
    lower = filename.lower()
    if lower.endswith(".vst3"):
        return "VST3"
    if lower.endswith(".clap"):
        return "CLAP"
    if "%flpath%" in lower or "\\plugins\\fruity\\" in lower:
        return "FL"
    if lower.endswith(".dll"):
        return "VST"
    return "FL" if group == "Fruity" else group if group in FORMAT_PRIORITY else ""


def _make_plugin(key: str, kind: str, group: str, source: str, fields: dict[str, str], fst: str | None,
                 nfo: str | None, install: str) -> Plugin:
    """Создаёт Plugin из полей индекса."""
    files = []
    try:
        count = int(fields.get("ps_files", "0"))
    except ValueError:
        count = 0
    for i in range(count):
        filename = fields.get(f"ps_file_filename_{i}", "")
        files.append(PluginFile(
            name=fields.get(f"ps_file_name_{i}", ""),
            filename=filename.replace("%FLPath%", install.rstrip("\\")) if install else filename,
            format=_file_format(filename, group),
            bits=fields.get(f"ps_file_bitsize_{i}", ""),
            vendor=fields.get(f"ps_file_vendorname_{i}", "").strip(),
            category=fields.get(f"ps_file_category_{i}", ""),
        ))
    flags = fields.get("ps_file_scanflags_0", "")
    type_known = bool(fields.get("ps_file_type_0"))
    name = fields.get("ps_name") or os.path.basename(key)
    ok = type_known and flags.isdigit() and bool(int(flags) & 1)
    plugin = Plugin(key=key, kind=kind, group=group, source=source, name=name, files=files, ok=ok,
                    type_known=type_known, fst=fst, nfo=nfo)
    plugin.installed = _delphi_date(fields.get("ps_file_date_0", ""))
    size = fields.get("ps_file_size_0", "")
    plugin.size = int(size) if size.isdigit() else 0
    return plugin


def _delphi_date(raw: str) -> float:
    """ps_file_date: дата Delphi TDateTime (дни с 30.12.1899), записанная битами double."""
    try:
        days = struct.unpack("<d", struct.pack("<q", int(raw)))[0]
    except (ValueError, struct.error):
        return 0.0
    return (days - 25569) * 86400 if 30000 < days < 80000 else 0.0


def _kind_from_fields(fields: dict[str, str], path: str) -> str:
    """Эффект или генератор: по типу в файле, иначе по пути."""
    kind = {"1": "Effects", "2": "Generators"}.get(fields.get("ps_file_type_0", ""))
    if kind:
        return kind
    return "Generators" if "generators" in path.casefold() else "Effects"


def load_installed(db: str, install: str = "") -> tuple[list[Plugin], list[Source]]:
    """Читает Installed: сначала индекс, затем .fst, которых в индексе нет."""
    installed = os.path.join(db, "Installed")
    index_path = os.path.join(installed, INDEX_FILE)
    index = parse_index(_read_text(index_path)) if os.path.isfile(index_path) else {}

    on_disk: dict[str, tuple[str, str, str, str]] = {}  # ключ в нижнем регистре -> (тип, папка, ключ, найденные расширения)
    groups: list[tuple[str, str]] = []
    for kind in KINDS:
        kind_dir = os.path.join(installed, kind)
        if not os.path.isdir(kind_dir):
            continue
        with os.scandir(kind_dir) as it:
            for group_entry in sorted((e for e in it if e.is_dir()), key=lambda e: e.name.casefold()):
                groups.append((kind, group_entry.name))
                with os.scandir(group_entry.path) as files:
                    for entry in files:
                        stem, ext = os.path.splitext(entry.name)
                        ext = ext.lower()
                        if ext in (".fst", ".nfo"):
                            key = f"{kind}\\{group_entry.name}\\{stem}"
                            old = on_disk.get(key.casefold(), (kind, group_entry.name, key, ""))
                            on_disk[key.casefold()] = (kind, group_entry.name, old[2], old[3] + ext)

    plugins: list[Plugin] = []
    seen: set[str] = set()
    for key, fields in index.items():
        parts = key.split("\\")
        if len(parts) < 3 or parts[0] not in KINDS:
            continue
        kind, group = parts[0], parts[1]
        info = on_disk.get(key.casefold())
        exts = info[3] if info else ""
        base = os.path.join(installed, key)
        fst = base + ".fst" if ".fst" in exts else None
        nfo = base + ".nfo" if ".nfo" in exts else None
        seen.add(key.casefold())
        plugins.append(_make_plugin(key, kind, group, f"{kind}\\{group}", fields, fst, nfo, install))

    # Файлы, которых нет в индексе, например из папок New.
    known = {(p.kind, p.name_id) for p in plugins}
    for folded, (kind, group, key, exts) in on_disk.items():
        if folded in seen or ".fst" not in exts:
            continue
        base = os.path.join(installed, key)
        nfo = base + ".nfo" if ".nfo" in exts else None
        fields = parse_nfo(_read_text(nfo)) if nfo else {}
        plugin = _make_plugin(key, kind, group, f"{kind}\\{group}", fields, base + ".fst", nfo, install)
        if group.casefold() == "new" and (kind, plugin.name_id) in known:
            continue  # этот плагин уже есть в папке своего формата
        if not nfo:
            plugin.ok = True  # FL Studio может работать и с одним .fst
        plugins.append(plugin)

    plugins = _merge_untyped_errors(plugins)
    for p in plugins:
        if p.fst and not p.raw_vendor:
            p.fst_vendor = read_fst_vendor(p.fst)

    counts: dict[str, int] = {}
    for p in plugins:
        counts[p.source] = counts.get(p.source, 0) + 1
    sources = []
    for kind, group in groups:
        sid = f"{kind}\\{group}"
        if counts.get(sid):
            label = "FL" if group == "Fruity" else group
            sources.append(Source(sid, label, f"Installed\\{kind}\\{group}\\", kind, count=counts[sid]))
    return plugins, sources


def _merge_untyped_errors(plugins: list[Plugin]) -> list[Plugin]:
    """FL пишет сломанный плагин и в эффекты, и в генераторы: показываем один раз."""
    seen: set[tuple[str, str]] = set()
    result = []
    for p in plugins:
        if not p.type_known and not p.fst:
            ident = (p.group, p.name_id)
            if ident in seen:
                continue
            seen.add(ident)
        result.append(p)
    return result


def load_custom(folder: str, install: str = "") -> tuple[list[Plugin], Source]:
    """Читает папку пользователя с парами .fst и .nfo."""
    sid = "custom:" + os.path.normcase(os.path.normpath(folder))
    plugins = []
    try:
        names = os.listdir(folder)
    except OSError:
        names = []
    lower = {n.lower(): n for n in names}
    for name in names:
        stem, ext = os.path.splitext(name)
        if ext.lower() != ".fst":
            continue
        fst = os.path.join(folder, name)
        nfo_name = lower.get((stem + ".nfo").lower())
        nfo = os.path.join(folder, nfo_name) if nfo_name else None
        fields = parse_nfo(_read_text(nfo)) if nfo else {}
        kind = _kind_from_fields(fields, folder)
        plugin = _make_plugin(f"{sid}\\{stem}", kind, "Custom", sid, fields, fst, nfo, install)
        plugin.name = fields.get("ps_name") or stem
        plugin.ok = True
        plugin.fst_vendor = "" if plugin.raw_vendor else read_fst_vendor(fst)
        plugins.append(plugin)
    label = tr("Папка")
    return plugins, Source(sid, label, folder.rstrip("\\") + "\\", None, custom=True, count=len(plugins))


def scan_organized(db: str) -> tuple[dict[tuple[str, str], str], dict[str, dict[str, str]]]:
    """Находит все .fst вне Installed.

    Возвращает {(тип, имя): папка} и для каждого типа {имя в нижнем регистре: настоящее имя},
    чтобы новая папка совпала по написанию с уже существующей.
    """
    organized: dict[tuple[str, str], str] = {}
    folders: dict[str, dict[str, str]] = {k: {} for k in KINDS}
    for kind in KINDS:
        root = os.path.join(db, kind)
        for current, dirs, files in os.walk(root):
            if current != root:
                folders[kind].setdefault(os.path.basename(current).casefold(), os.path.basename(current))
            for name in files:
                stem, ext = os.path.splitext(name)
                if ext.lower() == ".fst":
                    organized.setdefault((kind, stem.casefold()), current)
    return organized, folders


# --------------------------------------------------------------------------------------------
# Планирование
# --------------------------------------------------------------------------------------------
def safe_folder_name(vendor: str) -> str:
    """Превращает строку из файла в безопасное имя папки."""
    name = _FORBIDDEN.sub(" ", vendor)
    name = " ".join(name.split()).rstrip(". ")
    name = name.lstrip(". ")
    if not name:
        return UNKNOWN_VENDOR
    if name.split(".")[0].upper() in _RESERVED:
        name = "_" + name
    return name[:80].rstrip(". ")


def target_folder(db: str, plugin: Plugin, opts: Options, folders: dict[str, dict[str, str]]) -> str:
    """Папка назначения плагина по раскладке."""
    known = folders.get(plugin.kind, {})
    parts = [db, plugin.kind]
    template = opts.generators_layout if plugin.kind == "Generators" and opts.generators_layout else opts.layout
    for level in rules.layout_parts(template, plugin, opts.folder_language, opts.strip_suffix) or [UNKNOWN_VENDOR]:
        name = safe_folder_name(level)
        parts.append(known.get(name.casefold(), name))
    return os.path.join(*parts)


def _format_rank(p: Plugin, order: tuple = FORMAT_ORDER) -> tuple:
    """Чем меньше значение, тем предпочтительнее копия плагина."""
    rank = order.index(p.primary.format) if p.primary and p.primary.format in order else 9
    return (rank, -len(p.files))


def build_plan(plugins: list[Plugin], db: str, opts: Options, folders: dict[str, dict[str, str]]) -> Plan:
    """Составляет план: что копировать, что перемещать, что пропустить. Диск не меняет."""
    plan = Plan()
    candidates: list[Plugin] = []
    for p in plugins:
        if not p.fst:
            plan.skip("no_file")
        elif opts.skip_errors and not p.ok:
            plan.skip("error")
        elif p.organized_in and opts.reorganize:
            candidates.append(p)
        elif opts.skip_organized and p.organized_in:
            plan.skip("organized")
        else:
            candidates.append(p)
    if opts.one_copy:
        best: dict[tuple[str, str], Plugin] = {}
        for p in candidates:
            ident = (p.kind, p.name_id)
            current = best.get(ident)
            if current is None:
                best[ident] = p
            else:
                plan.skip("duplicate")
                if _format_rank(p, tuple(opts.format_order)) < _format_rank(current, tuple(opts.format_order)):
                    best[ident] = p
        candidates = list(best.values())
    for p in candidates:
        dest = target_folder(db, p, opts, folders)
        if opts.reorganize and p.organized_in:
            if os.path.normcase(os.path.normpath(p.organized_in)) == os.path.normcase(os.path.normpath(dest)):
                plan.skip("in_place")
            else:
                plan.actions.append(Action(p, dest, p.organized_in))
        else:
            plan.actions.append(Action(p, dest))
    plan.actions.sort(key=lambda a: (a.dest_dir.casefold(), a.plugin.name_id))
    return plan


def _inside(path: str, root: str) -> bool:
    """Лежит ли путь внутри папки root (и не равен ли ей)."""
    path, root = os.path.normcase(os.path.abspath(path)), os.path.normcase(os.path.abspath(root))
    try:
        return os.path.commonpath([path, root]) == root and path != root
    except ValueError:
        return False


def new_entries(plugin: Plugin, db: str) -> list[str]:
    """Файлы плагина в списке New, если у него есть настоящая запись в папке формата."""
    if not plugin.fst or plugin.group.casefold() == "new" or plugin.source.startswith("custom:"):
        return []
    stem = os.path.splitext(os.path.basename(plugin.fst))[0]
    folder = os.path.join(db, "Installed", plugin.kind, "New")
    return [path for path in (os.path.join(folder, stem + ext) for ext in (".fst", ".nfo")) if os.path.isfile(path)]


def _take_from_new(plugin: Plugin, db: str, result: RunResult) -> None:
    """Убирает плагин из списка New. Журнал хранит эти маленькие файлы для отмены."""
    for path in new_entries(plugin, db):
        with open(path, "rb") as f:
            data = f.read()
        os.remove(path)
        result.new_removed.append({"path": path, "data": base64.b64encode(data).decode("ascii")})


def execute(plan: Plan, db: str, opts: Options, progress=None, cancelled=None, log=None) -> RunResult:
    """Копирует .fst и .nfo по плану. В Installed может измениться только список New, и только по настройке."""
    result = RunResult()
    total = len(plan.actions)
    known_dirs: set[str] = set()
    for done, action in enumerate(plan.actions):
        if cancelled is not None and cancelled():
            result.cancelled = True
            break
        plugin = action.plugin
        try:
            if not _inside(action.dest_dir, db):
                raise ValueError(tr("папка назначения вне базы плагинов"))
            _ensure_dir(action.dest_dir, db, known_dirs, result)
            if action.move_from:
                _move_files(plugin, action.move_from, action.dest_dir, db, result)
                result.moved += 1
                if log is not None:
                    log("move", f"{plugin.name}: {os.path.relpath(action.move_from, db)} -> {os.path.relpath(action.dest_dir, db)}")
                if progress is not None:
                    progress(done + 1, total, plugin.name)
                continue
            dest_fst = os.path.join(action.dest_dir, os.path.basename(plugin.fst))
            if os.path.exists(dest_fst) and not opts.overwrite:
                result.skipped_existing += 1
            else:
                _copy(plugin.fst, dest_fst, result)
                if plugin.nfo and os.path.isfile(plugin.nfo):
                    _copy(plugin.nfo, os.path.join(action.dest_dir, os.path.basename(plugin.nfo)), result)
                result.copied += 1
                if log is not None:
                    log("copy", f"{plugin.name} -> {os.path.relpath(action.dest_dir, db)}")
            if opts.move_from_new:
                _take_from_new(plugin, db, result)
        except OSError as exc:
            result.errors.append((plugin.name, exc.strerror or str(exc)))
        except ValueError as exc:
            result.errors.append((plugin.name, str(exc)))
        if progress is not None:
            progress(done + 1, total, plugin.name)
    return result


def _ensure_dir(path: str, db: str, known: set[str], result: RunResult) -> None:
    """Создаёт папку и запоминает новые, чтобы отмена могла их убрать."""
    if path in known:
        return
    missing = []
    current = path
    while not os.path.isdir(current) and _inside(current, db):
        missing.append(current)
        current = os.path.dirname(current)
    os.makedirs(path, exist_ok=True)
    result.created_dirs.extend(reversed(missing))
    known.add(path)


def _move_files(plugin: Plugin, folder: str, dest_dir: str, db: str, result: RunResult | None = None) -> None:
    """Переносит .fst и .nfo между организованными папками. Installed не трогает."""
    if not _inside(folder, db) or _inside(folder, os.path.join(db, "Installed")) or not _inside(dest_dir, db):
        raise ValueError(tr("папка вне базы плагинов"))
    targets = [name for name in os.listdir(folder)
               if os.path.splitext(name)[0].casefold() == plugin.name_id and os.path.splitext(name)[1].lower() in (".fst", ".nfo")]
    for name in targets:
        if os.path.exists(os.path.join(dest_dir, name)):
            raise FileExistsError(tr("{name} уже есть в папке назначения").format(name=name))
    for name in targets:
        source, target = os.path.join(folder, name), os.path.join(dest_dir, name)
        os.replace(source, target)
        if result is not None:
            result.moved_files.append({"from": source, "to": target})
    _remove_empty(folder, db)


def _copy(src: str, dest: str, result: RunResult) -> None:
    """Копирует файл и запоминает его, если он новый."""
    existed = os.path.exists(dest)
    shutil.copy2(src, dest)
    if not existed:
        result.created_files.append({"path": dest, "size": os.path.getsize(dest)})


# --------------------------------------------------------------------------------------------
# Удаление и отмена
# --------------------------------------------------------------------------------------------
def recycle(paths: list[str]) -> bool:
    """Отправляет файлы в корзину. Возвращает True при успехе."""
    if not paths:
        return True

    class SHFILEOPSTRUCTW(ctypes.Structure):
        """Структура Windows для операции с файлами."""
        _fields_ = [("hwnd", wintypes.HWND), ("wFunc", wintypes.UINT), ("pFrom", wintypes.LPCWSTR),
                    ("pTo", wintypes.LPCWSTR), ("fFlags", ctypes.c_ushort), ("fAnyOperationsAborted", wintypes.BOOL),
                    ("hNameMappings", wintypes.LPVOID), ("lpszProgressTitle", wintypes.LPCWSTR)]

    buffer = ctypes.create_unicode_buffer("\0".join(paths) + "\0\0")
    op = SHFILEOPSTRUCTW()
    op.wFunc = 3  # FO_DELETE: удаление
    op.pFrom = ctypes.cast(buffer, wintypes.LPCWSTR)
    op.fFlags = 0x40 | 0x10 | 0x04 | 0x400  # в корзину, без вопросов и окон Windows
    return ctypes.windll.shell32.SHFileOperationW(ctypes.byref(op)) == 0 and not op.fAnyOperationsAborted


def remove_organized(plugin: Plugin, db: str, trash=recycle) -> None:
    """Убирает организованную копию. Вне Effects и Generators ничего не удаляет."""
    folder = plugin.organized_in
    if not folder or not any(_inside(folder, os.path.join(db, k)) or
                             os.path.normcase(folder) == os.path.normcase(os.path.join(db, k)) for k in KINDS):
        raise ValueError(tr("копия находится вне папок Effects и Generators"))
    targets = []
    for name in os.listdir(folder):
        stem, ext = os.path.splitext(name)
        if stem.casefold() == plugin.name_id and ext.lower() in (".fst", ".nfo"):
            targets.append(os.path.join(folder, name))
    if not trash(targets):
        raise OSError(tr("не удалось переместить файлы в корзину"))
    _remove_empty(folder, db)


def move_organized(plugin: Plugin, dest_dir: str, db: str) -> None:
    """Переносит копию в другую папку, например после смены производителя."""
    if not plugin.organized_in:
        raise ValueError(tr("папка вне базы плагинов"))
    os.makedirs(dest_dir, exist_ok=True)
    _move_files(plugin, plugin.organized_in, dest_dir, db)


def _remove_empty(folder: str, db: str) -> None:
    """Удаляет опустевшую папку и пустых родителей, но не Effects и Generators."""
    roots = {os.path.normcase(os.path.join(db, k)) for k in KINDS}
    current = folder
    while _inside(current, db) and os.path.normcase(current) not in roots:
        try:
            os.rmdir(current)  # сработает только для пустой папки
        except OSError:
            return
        current = os.path.dirname(current)


def write_journal(path: str, db: str, result: RunResult) -> None:
    """Записывает журнал последнего запуска для отмены."""
    payload = {"db": db, "time": time.time(), "files": result.created_files, "dirs": result.created_dirs,
               "moved": result.moved_files, "new_removed": result.new_removed}
    _write_json(path, payload)


def read_journal(path: str) -> dict | None:
    """Читает журнал отмены. None, если отменять нечего."""
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return data if data.get("files") or data.get("moved") or data.get("new_removed") else None
    except (OSError, ValueError):
        return None


def undo(journal_path: str, db: str, trash=recycle) -> tuple[int, int]:
    """Отменяет последний запуск. Удаляются только созданные им и не изменённые с тех пор файлы."""
    data = read_journal(journal_path)
    if not data or os.path.normcase(data.get("db", "")) != os.path.normcase(db):
        return 0, 0
    targets, kept = [], 0
    for item in data["files"]:
        path, size = item.get("path", ""), item.get("size", -1)
        if _inside(path, db) and not _inside(path, os.path.join(db, "Installed")) and \
                os.path.isfile(path) and os.path.getsize(path) == size:
            targets.append(path)
        else:
            kept += 1
    if not trash(targets):
        raise OSError(tr("не удалось переместить файлы в корзину"))
    restored = 0
    for item in reversed(data.get("moved", [])):
        source, target = item.get("to", ""), item.get("from", "")
        allowed = all(_inside(p, db) and not _inside(p, os.path.join(db, "Installed")) for p in (source, target))
        if allowed and os.path.isfile(source) and not os.path.exists(target):
            os.makedirs(os.path.dirname(target), exist_ok=True)
            os.replace(source, target)
            _remove_empty(os.path.dirname(source), db)
            restored += 1
        else:
            kept += 1
    for folder in reversed(data.get("dirs", [])):
        _remove_empty(folder, db)
    for item in data.get("new_removed", []):
        path = item.get("path", "")
        parts = os.path.normcase(os.path.relpath(path, db)).split(os.sep) if _inside(path, db) else []
        if len(parts) == 4 and parts[0] == "installed" and parts[2] == "new" and not os.path.exists(path):
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "wb") as f:
                f.write(base64.b64decode(item.get("data", "")))
            restored += 1
    os.remove(journal_path)
    return len(targets) + restored, kept


# --------------------------------------------------------------------------------------------
# Бэкапы
# --------------------------------------------------------------------------------------------
def list_backups(folder: str) -> list[str]:
    """Бэкапы этой программы, новые первыми."""
    try:
        names = [n for n in os.listdir(folder) if re.fullmatch(r"FODB-\d{8}-\d{6}(-\d+)?\.zip", n)]
    except OSError:
        return []
    return [os.path.join(folder, n) for n in sorted(names, reverse=True)]


def backup_database(db: str, folder: str, keep: int = 20) -> str:
    """Упаковывает базу в ZIP и возвращает путь. Архивы сверх keep удаляются."""
    os.makedirs(folder, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    target = os.path.join(folder, f"FODB-{stamp}.zip")
    serial = 1
    while os.path.exists(target):
        target = os.path.join(folder, f"FODB-{stamp}-{serial}.zip")
        serial += 1
    temp = target + ".tmp"
    try:
        with zipfile.ZipFile(temp, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
            for current, _dirs, files in os.walk(db):
                relative = os.path.relpath(current, db)
                if relative != ".":
                    archive.write(current, relative)  # сохраняет и пустые папки
                for name in files:
                    path = os.path.join(current, name)
                    archive.write(path, os.path.relpath(path, db))
        os.replace(temp, target)
    finally:
        if os.path.exists(temp):
            os.remove(temp)
    for old in list_backups(folder)[keep:]:
        os.remove(old)
    return target


def restore_backup(path: str, db: str, folder: str, trash=recycle, keep: int = 20) -> int:
    """Возвращает Effects и Generators к бэкапу. Installed принадлежит FL Studio и не меняется."""
    roots = tuple(k.casefold() + "/" for k in KINDS)
    with zipfile.ZipFile(path) as archive:
        wanted = {}
        for info in archive.infolist():
            name = info.filename.replace("\\", "/")
            parts = name.split("/")
            if info.is_dir() or ".." in parts or not name.casefold().startswith(roots):
                continue
            target = os.path.normpath(os.path.join(db, *parts))
            if _inside(target, db):
                wanted[os.path.normcase(target)] = (target, info)
        backup_database(db, folder, keep)  # страховочная копия текущего состояния
        surplus = []
        for kind in KINDS:
            for current, _dirs, files in os.walk(os.path.join(db, kind)):
                surplus.extend(os.path.join(current, n) for n in files if os.path.normcase(os.path.join(current, n)) not in wanted)
        if surplus and not trash(surplus):
            raise OSError(tr("не удалось переместить файлы в корзину"))
        for target, info in wanted.values():
            os.makedirs(os.path.dirname(target), exist_ok=True)
            with archive.open(info) as source, open(target, "wb") as out:
                shutil.copyfileobj(source, out)
    for kind in KINDS:  # папки, опустевшие после восстановления
        for current, dirs, files in os.walk(os.path.join(db, kind), topdown=False):
            if current != os.path.join(db, kind) and not dirs and not files:
                try:
                    os.rmdir(current)
                except OSError:
                    pass
    return len(wanted)


# --------------------------------------------------------------------------------------------
# Проверка обновлений
# --------------------------------------------------------------------------------------------
def version_tuple(text: str) -> tuple[int, ...]:
    """Числа из строки версии, чтобы версии можно было сравнивать."""
    return tuple(int(part) for part in re.findall(r"\d+", text))


def latest_release(repository: str) -> str | None:
    """Тег последнего релиза на GitHub. None, если релиза нет или нет сети.

    Запрос идёт через службу загрузки Windows, поэтому в программу не надо включать TLS-библиотеку.
    """
    target = os.path.join(tempfile.gettempdir(), f"fodb-release-{os.getpid()}.json")
    url = f"https://api.github.com/repos/{repository}/releases/latest?t={int(time.time())}"
    try:
        if ctypes.windll.urlmon.URLDownloadToFileW(None, url, target, 0, None) != 0:
            return None
        with open(target, encoding="utf-8") as f:
            return json.load(f).get("tag_name")
    except (OSError, ValueError, AttributeError):
        return None
    finally:
        if os.path.exists(target):
            os.remove(target)


# --------------------------------------------------------------------------------------------
# Журнал действий
# --------------------------------------------------------------------------------------------
class ActivityLog:
    """Текстовый журнал с пределом размера: сверх него старшая половина перезаписывается."""

    LIMIT = 20 * 1048576

    def __init__(self, path: str, limit: int = LIMIT):
        """path: файл журнала, limit: предел в байтах."""
        self.path, self.limit = path, limit

    def write(self, action: str, detail: str) -> None:
        """Добавляет строку с датой."""
        line = f"{time.strftime('%Y-%m-%d %H:%M:%S')}  {action:<8} {detail}\n".encode("utf-8", "replace")
        try:
            with open(self.path, "ab") as f:
                f.write(line)
                size = f.tell()
            if size > self.limit:
                self._trim()
        except OSError:
            pass  # сбой журнала не должен мешать работе

    def _trim(self) -> None:
        """Оставляет только новую половину файла."""
        with open(self.path, "rb") as f:
            f.seek(-(self.limit // 2), os.SEEK_END)
            tail = f.read()
        temp = self.path + ".tmp"
        with open(temp, "wb") as f:
            f.write(tail[tail.find(b"\n") + 1:])
        os.replace(temp, self.path)

    def tail(self, limit: int = 262144) -> str:
        """Последняя часть журнала в виде текста."""
        try:
            with open(self.path, "rb") as f:
                f.seek(0, os.SEEK_END)
                start = max(0, f.tell() - limit)
                f.seek(start)
                data = f.read()
        except OSError:
            return ""
        if start:
            data = data[data.find(b"\n") + 1:]
        return data.decode("utf-8", "replace")


# --------------------------------------------------------------------------------------------
# Портативные настройки
# --------------------------------------------------------------------------------------------
def app_dir() -> str:
    """Папка программы: рядом с exe или корень проекта при запуске из исходников."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def data_dir() -> str:
    """Данные лежат рядом с программой; если там нельзя писать, в профиле пользователя."""
    here = app_dir()
    probe = os.path.join(here, ".fodb_write_test")
    try:
        with open(probe, "w"):
            pass
        os.remove(probe)
        return here
    except OSError:
        fallback = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "FODB")
        os.makedirs(fallback, exist_ok=True)
        return fallback


def _write_json(path: str, payload: dict) -> None:
    """Пишет JSON через временный файл, чтобы сбой не испортил старый."""
    temp = path + ".tmp"
    with open(temp, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)
    os.replace(temp, path)


class Settings:
    """Настройки программы в файле FODB.json рядом с ней."""
    DEFAULTS = {
        "db": "", "disabled_sources": None, "custom_sources": [], "vendor_overrides": {},
        "one_copy": True, "skip_errors": True, "skip_organized": True, "overwrite": False, "reorganize": False,
        "only_filtered": True, "layout": "", "custom_layout": "", "filters": {}, "purpose_overrides": {}, "purpose_rules": [],
        "preview": True, "auto_backup": True, "column_order": [], "always_on_top": False, "language": "",
        "geometry": "", "left_width": 302, "column_widths": {}, "sort": ["vendor", False],
        "layout_generators": "", "folder_language": "", "format_order": list(FORMAT_ORDER), "move_from_new": True,
        "strip_suffix": False, "vendor_aliases": {}, "backup_keep": 40, "confirm_move": True, "confirm_delete": True,
        "confirm_restore": True, "startup_action": "propose", "close_action": "exit", "double_click": "plugin",
        "theme_mode": "fl", "custom_colors": {}, "ui_scale": 100, "font_family": "Segoe UI", "font_size": 11,
        "animations": True, "hidden_columns": [], "hotkeys": {}, "find_text": "", "main_tab": "plugins", "side_page": "options",
        "selected": [], "status_style": "text", "status_ok": "", "status_error": "", "maximized": False,
    }
    # Значения этого компьютера: в файл экспорта они не попадают.
    LOCAL_KEYS = ("db", "geometry", "maximized", "custom_sources")

    def __init__(self, folder: str | None = None):
        """Загружает настройки; неизвестные ключи игнорируются."""
        self.folder = folder or data_dir()
        self.path = os.path.join(self.folder, "FODB.json")
        self.journal = os.path.join(self.folder, "FODB.undo.json")
        self.backups = os.path.join(self.folder, "Backups")
        self.log = ActivityLog(os.path.join(self.folder, "FODB.log"))
        self.first_run = not os.path.exists(self.path)
        self.values = json.loads(json.dumps(self.DEFAULTS))  # глубокая копия: в значениях есть изменяемые списки и словари
        try:
            with open(self.path, encoding="utf-8") as f:
                loaded = json.load(f)
            if isinstance(loaded, dict):
                self.values.update({k: v for k, v in loaded.items() if k in self.DEFAULTS})
        except (OSError, ValueError):
            pass

    def __getitem__(self, key):
        """Чтение: settings["ключ"]."""
        return self.values[key]

    def __setitem__(self, key, value):
        """Запись: settings["ключ"] = значение."""
        self.values[key] = value

    def save(self) -> None:
        """Сохраняет настройки. Ошибка записи не мешает работе."""
        try:
            _write_json(self.path, self.values)
        except OSError:
            pass

    def export_to(self, path: str) -> None:
        """Сохраняет настройки в файл, без значений этого компьютера."""
        _write_json(path, {k: v for k, v in self.values.items() if k not in self.LOCAL_KEYS})

    def import_from(self, path: str) -> int:
        """Загружает файл из export_to. Неизвестные ключи и значения неверного типа пропускаются."""
        with open(path, encoding="utf-8") as f:
            loaded = json.load(f)
        count = 0
        for key, value in loaded.items() if isinstance(loaded, dict) else ():
            default = self.DEFAULTS.get(key, ...)
            if key in self.LOCAL_KEYS or default is ... or (default is not None and type(value) is not type(default)):
                continue
            self.values[key] = value
            count += 1
        if not count:
            raise ValueError(tr("Это не файл настроек FODB."))
        return count
