"""Тесты настроек: перенос из New, журнал, производители, горячие клавиши, экспорт."""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(__file__))
from test_core import Fixture, core  # noqa: E402

import hotkeys  # noqa: E402
import i18n  # noqa: E402
import rules  # noqa: E402
import theme  # noqa: E402


class MoveFromNewTests(Fixture):
    """Плагин уходит из списка New только по настройке, а отмена его возвращает."""

    def setUp(self):
        super().setUp()
        self.add("Effects\\VST3\\Alpha")
        self.add("Effects\\New\\Alpha", indexed=False)
        plugins, _sources, _folders = self.load()
        self.alpha = next(p for p in plugins if p.name == "Alpha")

    def organize(self, move: bool):
        """Раскладывает плагин и записывает журнал отмены."""
        opts = core.Options(move_from_new=move)
        result = core.execute(core.build_plan([self.alpha], self.db, opts, {}), self.db, opts)
        core.write_journal(os.path.join(self.tmp.name, "undo.json"), self.db, result)

    def test_entry_stays_when_option_is_off(self):
        self.organize(False)
        self.assertEqual(len(core.new_entries(self.alpha, self.db)), 2)

    def test_entry_leaves_and_undo_brings_it_back(self):
        self.organize(True)
        self.assertEqual(core.new_entries(self.alpha, self.db), [])
        self.assertTrue(os.path.isfile(self.alpha.fst), "настоящая запись плагина должна остаться")
        core.undo(os.path.join(self.tmp.name, "undo.json"), self.db, trash=lambda paths: [os.remove(p) for p in paths] or True)
        self.assertEqual(len(core.new_entries(self.alpha, self.db)), 2)


class FormatOrderTests(Fixture):
    """При одной копии выбирается формат, стоящий в порядке первым."""

    def test_order_decides_which_copy_is_made(self):
        self.add("Effects\\VST3\\Beta", filename="C:\\x\\Beta.vst3")
        self.add("Effects\\VST\\Beta", filename="C:\\x\\Beta.dll")
        plugins, _ = core.load_installed(self.db)
        opts = core.Options(format_order=("VST", "VST3", "CLAP", "FL"))
        plan = core.build_plan(plugins, self.db, opts, {})
        self.assertEqual([a.plugin.group for a in plan.actions], ["VST"])


class ActivityLogTests(unittest.TestCase):
    """Журнал не растёт сверх предела."""

    def test_log_stays_under_the_cap_and_keeps_the_newest(self):
        with tempfile.TemporaryDirectory() as folder:
            log = core.ActivityLog(os.path.join(folder, "a.log"), limit=2000)
            for i in range(500):
                log.write("copy", f"line {i}")
            self.assertLessEqual(os.path.getsize(log.path), 2100)
            self.assertIn("line 499", log.tail())
            self.assertNotIn("line 0\n", log.tail())


class VendorTests(unittest.TestCase):
    """Очистка и замена имён производителей."""

    def test_legal_suffixes_are_removed(self):
        self.assertEqual(rules.clean_vendor("Valhalla DSP, LLC"), "Valhalla DSP")
        self.assertEqual(rules.clean_vendor("Native Instruments GmbH"), "Native Instruments")
        self.assertEqual(rules.clean_vendor("Image-Line"), "Image-Line")
        self.assertEqual(rules.clean_vendor("Inc."), "Inc.")

    def test_alias_ignores_case(self):
        self.assertEqual(rules.apply_alias("DIRECT", {"direct": "MiniMeters"}), "MiniMeters")
        self.assertEqual(rules.apply_alias("Other", {"direct": "MiniMeters"}), "Other")


class HotkeyTests(unittest.TestCase):
    """Горячие клавиши."""

    def test_shortcut_text(self):
        self.assertEqual(hotkeys.shortcut(70, hotkeys.CTRL), "Ctrl+F")
        self.assertEqual(hotkeys.shortcut(116, 0), "F5")
        self.assertEqual(hotkeys.shortcut(70, 0), "", "простая буква нужна для ввода текста")
        self.assertEqual(hotkeys.shortcut(17, hotkeys.CTRL), "")

    def test_assigning_takes_the_shortcut_from_another_action(self):
        saved = hotkeys.assign({}, "tab_about", "Ctrl+1")
        self.assertEqual(saved["tab_about"], "Ctrl+1")
        self.assertEqual(saved["tab_plugins"], "")
        self.assertEqual(hotkeys.bindings(saved)["Ctrl+1"], "tab_about")


class SettingsFileTests(unittest.TestCase):
    """Экспорт и импорт настроек."""

    def test_export_skips_computer_specific_values(self):
        with tempfile.TemporaryDirectory() as folder:
            settings = core.Settings(folder)
            settings["db"], settings["backup_keep"] = "C:\\db", 15
            path = os.path.join(folder, "out.json")
            settings.export_to(path)
            with open(path, encoding="utf-8") as f:
                self.assertNotIn("db", json.load(f))
            settings["backup_keep"] = 40
            settings.import_from(path)
            self.assertEqual(settings["backup_keep"], 15)

    def test_foreign_file_is_refused(self):
        with tempfile.TemporaryDirectory() as folder:
            settings = core.Settings(folder)
            path = os.path.join(folder, "bad.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump({"backup_keep": "много", "foo": 1}, f)
            with self.assertRaises(ValueError):
                settings.import_from(path)
            self.assertEqual(settings["backup_keep"], 40)


class OtherTests(unittest.TestCase):
    """Версии, своя палитра и язык папок."""

    def test_version_comparison(self):
        self.assertGreater(core.version_tuple("v1.1.0.0612"), core.version_tuple("1.1.0.0611"))

    def test_custom_palette_uses_the_picked_panel(self):
        palette = theme.custom_palette({"PANEL": "#334455"})
        self.assertEqual(palette["PANEL"], "#334455")
        self.assertEqual(set(palette), set(theme.DEFAULT_PALETTE))

    def test_folder_names_can_use_another_language(self):
        i18n.set_language("ru")
        self.assertEqual(i18n.tr_in("EN-en", "Реверберация"), "Reverb")
        self.assertEqual(i18n.tr_in("", "Реверберация"), "Реверберация")


if __name__ == "__main__":
    unittest.main()
