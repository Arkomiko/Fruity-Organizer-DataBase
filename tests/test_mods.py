"""Моды: поиск, включение, обработчики и защита от ошибок. Окна здесь не открываются."""
import json
import os
import shutil
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

import core
import mods
import rules


class FakeSettings(dict):
    """Настройки в виде словаря с папкой данных."""
    folder = ""


def manager(active, enabled=True):
    """Менеджер с выбранными модами и временной папкой данных."""
    settings = FakeSettings(mods_enabled=enabled, mods_active=list(active))
    settings.folder = tempfile.mkdtemp()
    result = mods.Manager(SimpleNamespace(s=settings, db=settings.folder))
    result.reload()
    return result


def plugin(name, kind="Effects", vendor="", organized=None, group="VST3"):
    """Плагин для проверки."""
    item = core.Plugin(key=name, kind=kind, group=group, source="s", name=name, files=[core.PluginFile(name, name + ".dll", "VST3", "64", vendor, "")],
                       ok=True, type_known=True, fst=None, nfo=None)
    item.organized_in = organized
    return item


class ModsTest(unittest.TestCase):
    def tearDown(self):
        for purpose_id in list(rules.EXTRA_LABELS):
            rules.remove_purpose(purpose_id)

    def test_all_five_mods_are_found(self):
        ids = {info.id for info in mods.discover()}
        self.assertLessEqual({"Advenced purpose rules (experimentally)", "Other Integration BD (experimentally)", "Improving the algorithm for Determining Purpose (experimentally)", "Preview Tree", "Status Indicators (experimentally)"}, ids)

    def test_every_mod_folder_is_named_after_its_mod(self):
        for info in mods.discover():
            self.assertEqual(os.path.basename(info.folder), info.name)
            self.assertTrue(os.path.exists(os.path.join(info.folder, "index.json")))
            self.assertTrue(os.path.exists(os.path.join(info.folder, info.entry)))

    def test_first_enable_copies_mods_next_to_the_program(self):
        target = os.path.join(tempfile.mkdtemp(), "mods")
        with mock.patch.object(mods, "user_folder", return_value=target):
            mods.install_bundled()
            self.assertEqual({info.name for info in mods.discover()}, {info.name for info in mods.discover()} | {"Preview Tree"})
            shutil.rmtree(os.path.join(target, "Preview Tree"))
            mods.install_bundled()
            self.assertFalse(os.path.exists(os.path.join(target, "Preview Tree")), "удалённый мод не возвращается")

    def test_disabled_switch_loads_nothing(self):
        result = manager(["Status Indicators (experimentally)"], enabled=False)
        self.assertEqual(result.hooks, {})

    def test_each_mod_activates_without_errors(self):
        result = manager([info.id for info in mods.discover()])
        self.assertEqual({info.id: info.error for info in result.mods if info.error}, {})

    def test_rules_table_uses_real_purposes(self):
        with open(os.path.join(mods.bundled_folder(), "Advenced purpose rules (experimentally)", "rules.json"), encoding="utf-8") as f:
            table = json.load(f)
        self.assertGreater(len(table), 200)
        self.assertEqual({v for v in table.values() if v not in rules.PURPOSES}, set())

    def test_catalog_uses_real_purposes(self):
        with open(os.path.join(mods.bundled_folder(), "Other Integration BD (experimentally)", "catalog.json"), encoding="utf-8") as f:
            catalog = json.load(f)
        self.assertEqual({v["purpose"] for v in catalog.values() if v["purpose"] not in rules.PURPOSES}, set())

    def test_advanced_rules_classify_a_plugin(self):
        result = manager(["Advenced purpose rules (experimentally)"])
        purposes, source = rules.classify(plugin("Decapitator"), None, None, result.purpose_hooks())
        self.assertEqual((purposes, source), (["distortion"], "mod"))

    def test_manual_choice_beats_a_mod(self):
        result = manager(["Advenced purpose rules (experimentally)"])
        item = plugin("Decapitator")
        purposes, source = rules.classify(item, {item.name_id: "eq"}, None, result.purpose_hooks())
        self.assertEqual((purposes, source), (["eq"], "manual"))

    def test_catalog_fills_a_missing_vendor(self):
        result = manager(["Other Integration BD (experimentally)"])
        self.assertEqual(result.vendor(plugin("Serum")), "Xfer Records")
        self.assertEqual(result.vendor(plugin("Unknown Thing")), "")

    def test_finer_purposes_come_and_go_with_the_mod(self):
        result = manager(["Improving the algorithm for Determining Purpose (experimentally)"])
        self.assertIn("transient", rules.PURPOSES)
        purposes, _source = rules.classify(plugin("Transient Master"), None, None, result.purpose_hooks())
        self.assertEqual(purposes, ["transient"])
        self.assertEqual(rules.purpose_label("transient"), "Транзиент-шейперы" if rules.i18n.LANG == "RU-ru" else rules.EXTRA_LABELS["transient"].get(rules.i18n.LANG, "Transient shapers"))
        result.app.s["mods_active"] = []
        result.reload()
        self.assertNotIn("transient", rules.PURPOSES)

    def test_learning_applies_to_the_family(self):
        result = manager(["Improving the algorithm for Determining Purpose (experimentally)"])
        result.purpose_changed([plugin("Acme Space One", vendor="Acme")], "reverb")
        hooks = result.purpose_hooks()
        self.assertEqual(rules.classify(plugin("Acme Space Two", vendor="Acme"), None, None, hooks)[0], ["reverb"])
        self.assertNotEqual(rules.classify(plugin("Other Tool", vendor="Beta"), None, None, hooks)[0], ["reverb"])

    def test_status_colors(self):
        result = manager(["Status Indicators (experimentally)"])
        self.assertEqual(result.marker(plugin("A", organized="X:\\db\\Effects\\Vendor")), "#5FC46E")
        self.assertEqual(result.marker(plugin("A", organized="X:\\db\\Effects\\Избранное")), "#FFB23E")
        self.assertEqual(result.marker(plugin("A", group="New")), "#4A9BF0")
        self.assertIsNone(result.marker(plugin("A")))

    def test_broken_hook_is_switched_off(self):
        result = manager([])
        info = mods.ModInfo("x", "x", "", "", "", {}, "")

        def broken(_plugin):
            raise ValueError("boom")

        result.add_hook("marker", info, broken)
        self.assertIsNone(result.marker(plugin("A")))
        self.assertIn("boom", info.error)
        self.assertEqual(result.hooks["marker"], [])

    def test_broken_mod_file_does_not_stop_others(self):
        folder = tempfile.mkdtemp()
        os.makedirs(os.path.join(folder, "bad"))
        with open(os.path.join(folder, "bad", "index.json"), "w", encoding="utf-8") as f:
            json.dump({"name": "Bad"}, f)
        with open(os.path.join(folder, "bad", "mod.py"), "w", encoding="utf-8") as f:
            f.write("raise RuntimeError('broken mod')\n")
        info = mods.read_manifest(os.path.join(folder, "bad"))
        result = manager([])
        result._activate(info)
        self.assertIn("broken mod", info.error)


if __name__ == "__main__":
    unittest.main()
