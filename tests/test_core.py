"""Тесты логики раскладки на искусственной базе во временной папке."""
import os
import struct
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import core  # noqa: E402


def fst_bytes(vendor: str) -> bytes:
    """Содержимое .fst с производителем в конце."""
    raw = vendor.encode()
    return b"FLhd\x06\0\0\0" + b"\x01" * 40 + b"8\0\0\0" + struct.pack("<I", len(raw)) + b"\0\0\0\0" + raw


def section(key: str, name: str, filename: str, vendor: str = "", kind: str = "1", flags: str = "1") -> str:
    """Секция индекса для одного плагина."""
    lines = [f"[{key}]", "fileversion=2", f"ps_name={name}", "ps_files=1", f"ps_file_name_0={name}",
             f"ps_file_filename_0={filename}", "ps_file_bitsize_0=64", f"ps_file_scanflags_0={flags}"]
    if kind:
        lines.append(f"ps_file_type_0={kind}")
    if vendor:
        lines.append(f"ps_file_vendorname_0={vendor}")
    return "\r\n".join(lines) + "\r\n\r\n"


class Fixture(unittest.TestCase):
    """Временная база и помощники для её наполнения."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = os.path.join(self.tmp.name, "Plugin database")
        self.index = ""

    def tearDown(self):
        self.tmp.cleanup()

    def add(self, key, name=None, filename="C:\\VST3\\x.vst3", vendor="Acme", fst_vendor=None, kind="1", flags="1",
            make_fst=True, make_nfo=True, indexed=True):
        """Добавляет плагин в базу."""
        name = name or os.path.basename(key)
        base = os.path.join(self.db, "Installed", key)
        os.makedirs(os.path.dirname(base), exist_ok=True)
        if make_fst:
            with open(base + ".fst", "wb") as f:
                f.write(fst_bytes(vendor if fst_vendor is None else fst_vendor))
        text = section(key, name, filename, vendor, kind, flags)
        if make_nfo:
            with open(base + ".nfo", "w", encoding="utf-8", newline="") as f:
                f.write(text.split("\r\n", 1)[1])
        if indexed:
            self.index += text

    def load(self):
        """Записывает индекс и читает базу."""
        os.makedirs(os.path.join(self.db, "Installed"), exist_ok=True)
        with open(os.path.join(self.db, "Installed", core.INDEX_FILE), "w", encoding="utf-8-sig", newline="") as f:
            f.write(self.index)
        plugins, sources = core.load_installed(self.db, "M:\\FL")
        organized, folders = core.scan_organized(self.db)
        for p in plugins:
            p.vendor = p.raw_vendor or core.UNKNOWN_VENDOR
            p.organized_in = organized.get((p.kind, p.name_id))
        return plugins, sources, folders

    def organize(self, opts=None):
        """Составляет план и выполняет его."""
        plugins, _, folders = self.load()
        opts = opts or core.Options()
        plan = core.build_plan(plugins, self.db, opts, folders)
        return plan, core.execute(plan, self.db, opts)

    def path(self, *parts):
        """Путь внутри базы."""
        return os.path.join(self.db, *parts)


class ParsingTests(Fixture):
    """Чтение индекса и файлов плагинов."""

    def test_formats_status_and_fst_vendor_fallback(self):
        self.add("Effects\\VST3\\A", filename="C:\\x\\A.vst3")
        self.add("Effects\\CLAP\\B", filename="C:\\x\\B.clap")
        self.add("Effects\\VST\\C", filename="C:\\x\\C_x64.dll", vendor="", fst_vendor="FromTail")
        self.add("Effects\\Fruity\\D", filename="%FLPath%\\Plugins\\Fruity\\Effects\\D\\D_x64.dll", vendor="Image-Line", fst_vendor="")
        plugins, sources, _ = self.load()
        by = {p.name: p for p in plugins}
        self.assertEqual(by["A"].formats, "VST3")
        self.assertEqual(by["B"].formats, "CLAP")
        self.assertEqual(by["C"].formats, "VST")
        self.assertEqual(by["C"].raw_vendor, "FromTail")
        self.assertEqual(by["D"].formats, "FL")
        self.assertTrue(by["D"].directory.startswith("M:\\FL\\Plugins"))
        self.assertIn("FL", {s.label for s in sources})

    def test_new_folder_duplicates_are_hidden_but_unique_entries_stay(self):
        self.add("Effects\\VST3\\Same")
        self.add("Effects\\New\\Same", indexed=False)
        self.add("Effects\\New\\OnlyNew", indexed=False)
        plugins, _, _ = self.load()
        self.assertEqual(sorted(p.key for p in plugins), ["Effects\\New\\OnlyNew", "Effects\\VST3\\Same"])

    def test_failed_plugin_listed_under_both_kinds_appears_once(self):
        self.add("Effects\\VST\\Bad", vendor="", kind="", flags="34", make_fst=False)
        self.add("Generators\\VST\\Bad", vendor="", kind="", flags="34", make_fst=False)
        plugins, _, _ = self.load()
        self.assertEqual(len(plugins), 1)
        self.assertFalse(plugins[0].ok)

    def test_corrupt_fst_and_missing_nfo_do_not_crash(self):
        self.add("Effects\\VST\\NoNfo", make_nfo=False, indexed=False)
        junk = self.path("Installed", "Effects", "VST", "Junk.fst")
        with open(junk, "wb") as f:
            f.write(b"\xff\xfe\x00garbage")
        plugins, _, _ = self.load()
        self.assertEqual({p.name for p in plugins}, {"NoNfo", "Junk"})
        self.assertEqual(core.read_fst_vendor(junk), "")


class VendorFolderTests(unittest.TestCase):
    """Безопасные имена папок."""

    def test_unsafe_names_cannot_escape_or_break_paths(self):
        cases = {"..\\..\\Windows": "Windows", "A/B:C": "A B C", "Trailing Inc.": "Trailing Inc", "": "Unknown",
                 "...": "Unknown", "CON": "_CON", "Valhalla DSP, LLC": "Valhalla DSP, LLC", "nul.txt": "_nul.txt"}
        for raw, expected in cases.items():
            self.assertEqual(core.safe_folder_name(raw), expected, raw)


class OrganizeTests(Fixture):
    """Раскладка плагинов."""

    def test_copies_fst_and_nfo_into_vendor_folder_and_keeps_sources(self):
        self.add("Effects\\VST3\\Comp", vendor="Acme")
        self.add("Generators\\VST3\\Synth", vendor="Acme", kind="2")
        _, result = self.organize()
        self.assertEqual(result.copied, 2)
        for rel in (("Effects", "Acme", "Comp.fst"), ("Effects", "Acme", "Comp.nfo"), ("Generators", "Acme", "Synth.fst")):
            self.assertTrue(os.path.isfile(self.path(*rel)), rel)
        self.assertTrue(os.path.isfile(self.path("Installed", "Effects", "VST3", "Comp.fst")))

    def test_user_subfolder_option(self):
        self.add("Effects\\VST3\\Comp")
        self.organize(core.Options(layout="USER\\{vendor}"))
        self.assertTrue(os.path.isfile(self.path("Effects", "USER", "Acme", "Comp.fst")))

    def test_one_copy_prefers_vst3(self):
        self.add("Effects\\VST\\Comp", filename="C:\\x\\Comp.dll", vendor="ViaVst")
        self.add("Effects\\CLAP\\Comp", filename="C:\\x\\Comp.clap", vendor="ViaClap")
        self.add("Effects\\VST3\\Comp", filename="C:\\x\\Comp.vst3", vendor="ViaVst3")
        plan, result = self.organize()
        self.assertEqual(result.copied, 1)
        self.assertEqual(plan.skipped.get("duplicate"), 2)
        self.assertTrue(os.path.isfile(self.path("Effects", "ViaVst3", "Comp.fst")))

    def test_already_organized_anywhere_is_skipped(self):
        self.add("Effects\\VST3\\Comp")
        os.makedirs(self.path("Effects", "My Folder"))
        with open(self.path("Effects", "My Folder", "Comp.fst"), "wb") as f:
            f.write(b"mine")
        plan, result = self.organize()
        self.assertEqual(result.copied, 0)
        self.assertEqual(plan.skipped.get("organized"), 1)
        self.assertFalse(os.path.exists(self.path("Effects", "Acme")))

    def test_existing_file_kept_unless_overwrite_requested(self):
        self.add("Effects\\VST3\\Comp")
        os.makedirs(self.path("Effects", "Acme"))
        target = self.path("Effects", "Acme", "Comp.fst")
        with open(target, "wb") as f:
            f.write(b"mine")
        _, result = self.organize(core.Options(skip_organized=False))
        self.assertEqual(result.skipped_existing, 1)
        with open(target, "rb") as f:
            self.assertEqual(f.read(), b"mine")
        self.organize(core.Options(skip_organized=False, overwrite=True))
        with open(target, "rb") as f:
            self.assertNotEqual(f.read(), b"mine")

    def test_vendor_case_variants_share_one_folder(self):
        os.makedirs(self.path("Effects", "Dada Life"))
        self.add("Effects\\VST3\\One", vendor="DADA LIFE")
        self.organize()
        self.assertIn("Dada Life", os.listdir(self.path("Effects")))
        self.assertNotIn("DADA LIFE", os.listdir(self.path("Effects")))

    def test_errors_skipped_and_reported_without_stopping(self):
        self.add("Effects\\VST\\Bad", flags="2", vendor="X")
        self.add("Effects\\VST3\\Good")
        plugins, _, folders = self.load()
        plan = core.build_plan(plugins, self.db, core.Options(), folders)
        self.assertEqual([a.plugin.name for a in plan.actions], ["Good"])
        self.assertEqual(plan.skipped.get("error"), 1)
        plan.actions[0].plugin.fst += ".missing"
        self.add("Effects\\VST3\\Other")
        plugins, _, folders = self.load()
        plan = core.build_plan(plugins, self.db, core.Options(), folders)
        first = plan.actions[0].plugin
        first.fst += ".missing"
        result = core.execute(plan, self.db, core.Options())
        self.assertEqual(len(result.errors), 1)
        self.assertEqual(result.copied, 1)

    def test_destination_outside_database_is_refused(self):
        self.add("Effects\\VST3\\Comp")
        plugins, _, folders = self.load()
        plan = core.build_plan(plugins, self.db, core.Options(), folders)
        plan.actions[0].dest_dir = os.path.join(self.tmp.name, "outside")
        result = core.execute(plan, self.db, core.Options())
        self.assertEqual(result.copied, 0)
        self.assertFalse(os.path.exists(os.path.join(self.tmp.name, "outside")))

    def test_cancel_stops_early(self):
        for i in range(5):
            self.add(f"Effects\\VST3\\P{i}")
        plugins, _, folders = self.load()
        plan = core.build_plan(plugins, self.db, core.Options(), folders)
        calls = []
        result = core.execute(plan, self.db, core.Options(), lambda *a: calls.append(a), lambda: len(calls) >= 2)
        self.assertTrue(result.cancelled)
        self.assertEqual(result.copied, 2)


def delete_now(paths):
    for path in paths:
        os.remove(path)
    return True


class UndoAndRemoveTests(Fixture):
    """Отмена и удаление копий."""

    def test_undo_removes_only_unchanged_created_files(self):
        self.add("Effects\\VST3\\A", vendor="V1")
        self.add("Effects\\VST3\\B", vendor="V2")
        _, result = self.organize()
        journal = os.path.join(self.tmp.name, "undo.json")
        core.write_journal(journal, self.db, result)
        changed = self.path("Effects", "V2", "B.fst")
        with open(changed, "ab") as f:
            f.write(b"edited")
        removed, kept = core.undo(journal, self.db, trash=delete_now)
        self.assertEqual((removed, kept), (3, 1))
        self.assertFalse(os.path.exists(self.path("Effects", "V1")))
        self.assertTrue(os.path.isfile(changed))
        self.assertFalse(os.path.exists(journal))
        self.assertTrue(os.path.isfile(self.path("Installed", "Effects", "VST3", "A.fst")))

    def test_undo_ignores_journal_paths_outside_or_in_installed(self):
        self.add("Effects\\VST3\\A")
        protected = self.path("Installed", "Effects", "VST3", "A.fst")
        outside = os.path.join(self.tmp.name, "outside.txt")
        with open(outside, "w") as f:
            f.write("x")
        result = core.RunResult(created_files=[{"path": protected, "size": os.path.getsize(protected)},
                                               {"path": outside, "size": 1}])
        journal = os.path.join(self.tmp.name, "undo.json")
        core.write_journal(journal, self.db, result)
        self.assertEqual(core.undo(journal, self.db, trash=delete_now), (0, 2))
        self.assertTrue(os.path.isfile(protected) and os.path.isfile(outside))

    def test_remove_refuses_installed_and_removes_empty_vendor_folder(self):
        self.add("Effects\\VST3\\A")
        self.organize()
        plugins, _, _ = self.load()
        plugin = plugins[0]
        self.assertTrue(plugin.organized_in.endswith("Acme"))
        core.remove_organized(plugin, self.db, trash=delete_now)
        self.assertFalse(os.path.exists(self.path("Effects", "Acme")))
        self.assertTrue(os.path.isfile(plugin.fst))
        plugin.organized_in = self.path("Installed", "Effects", "VST3")
        with self.assertRaises(ValueError):
            core.remove_organized(plugin, self.db, trash=delete_now)
        self.assertTrue(os.path.isfile(plugin.fst))

    def test_move_after_vendor_change(self):
        self.add("Effects\\VST3\\A", vendor="Direct")
        self.organize()
        plugins, _, _ = self.load()
        core.move_organized(plugins[0], self.path("Effects", "Real Vendor"), self.db)
        self.assertTrue(os.path.isfile(self.path("Effects", "Real Vendor", "A.fst")))
        self.assertTrue(os.path.isfile(self.path("Effects", "Real Vendor", "A.nfo")))
        self.assertFalse(os.path.exists(self.path("Effects", "Direct")))


class CustomSourceTests(Fixture):
    """Своя папка с плагинами."""

    def test_custom_folder_reads_vendor_from_nfo_or_fst(self):
        folder = os.path.join(self.tmp.name, "custom")
        os.makedirs(folder)
        with open(os.path.join(folder, "One.FST"), "wb") as f:
            f.write(fst_bytes("TailVendor"))
        plugins, source = core.load_custom(folder)
        self.assertEqual(source.count, 1)
        self.assertEqual(plugins[0].raw_vendor, "TailVendor")
        self.assertEqual(plugins[0].kind, "Effects")


class SettingsTests(unittest.TestCase):
    """Файл настроек."""

    def test_round_trip_and_corrupt_file(self):
        with tempfile.TemporaryDirectory() as folder:
            settings = core.Settings(folder)
            settings["db"] = "X"
            settings.save()
            self.assertEqual(core.Settings(folder)["db"], "X")
            with open(settings.path, "w") as f:
                f.write("{broken")
            self.assertEqual(core.Settings(folder)["db"], "")


class BackupTests(Fixture):
    """Бэкапы и восстановление."""

    def setUp(self):
        super().setUp()
        self.add("Effects\\VST3\\Comp")
        self.organize()
        self.backups = os.path.join(self.tmp.name, "Backups")

    def test_backup_contains_whole_database(self):
        path = core.backup_database(self.db, self.backups)
        with zipfile.ZipFile(path) as z:
            names = set(z.namelist())
        self.assertIn("Effects/Acme/Comp.fst", names)
        self.assertIn("Installed/Effects/VST3/Comp.fst", names)

    def test_restore_returns_organized_folders_only(self):
        path = core.backup_database(self.db, self.backups)
        added = self.path("Effects", "Later", "New.fst")
        os.makedirs(os.path.dirname(added))
        with open(added, "w") as f:
            f.write("later")
        os.remove(self.path("Effects", "Acme", "Comp.fst"))
        fresh = self.path("Installed", "Effects", "VST3", "Fresh.fst")
        with open(fresh, "w") as f:
            f.write("scanned after the backup")
        core.restore_backup(path, self.db, self.backups, trash=delete_now)
        self.assertTrue(os.path.isfile(self.path("Effects", "Acme", "Comp.fst")))
        self.assertFalse(os.path.exists(added))
        self.assertTrue(os.path.isfile(fresh))
        self.assertEqual(len(core.list_backups(self.backups)), 2)  # вместе со страховочной копией

    def test_restore_ignores_entries_escaping_the_database(self):
        os.makedirs(self.backups)
        evil = os.path.join(self.backups, "evil.zip")
        with zipfile.ZipFile(evil, "w") as z:
            z.writestr("../../outside.txt", "x")
            z.writestr("Effects/../../../outside2.txt", "x")
            z.writestr("Installed/Effects/VST3/Comp.fst", "overwritten")
            z.writestr("Effects/Good/Fine.fst", "ok")
        core.restore_backup(evil, self.db, self.backups, trash=delete_now)
        self.assertTrue(os.path.isfile(self.path("Effects", "Good", "Fine.fst")))
        self.assertFalse(os.path.exists(os.path.join(self.tmp.name, "outside.txt")))
        with open(self.path("Installed", "Effects", "VST3", "Comp.fst"), "rb") as f:
            self.assertNotEqual(f.read(), b"overwritten")

    def test_old_backups_are_pruned(self):
        os.makedirs(self.backups)
        for i in range(25):
            with open(os.path.join(self.backups, f"FODB-20200101-0000{i:02}.zip"), "w") as f:
                f.write("x")
        core.backup_database(self.db, self.backups, keep=20)
        self.assertEqual(len(core.list_backups(self.backups)), 20)
        with open(os.path.join(self.backups, "notes.txt"), "w") as f:
            f.write("mine")
        core.backup_database(self.db, self.backups, keep=1)
        self.assertTrue(os.path.isfile(os.path.join(self.backups, "notes.txt")))


if __name__ == "__main__":
    unittest.main()
