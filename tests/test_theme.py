"""Тесты чтения тем FL Studio и таблиц языков."""
import os
import re
import sys
import tempfile
import unittest

SRC = os.path.join(os.path.dirname(__file__), "..", "src")
sys.path.insert(0, SRC)
import i18n  # noqa: E402
import theme  # noqa: E402

SAMPLE = "﻿Hue=0\nSaturation=0\nLightness=-153\nContrast=-8\nText=0\nSelected=11068490\nHighlight=-12283141\nMute=577656\nOption=-14135064\nTextColor=-3551277\n"


class ColorTests(unittest.TestCase):
    """Расчёт цветов."""

    def test_tcolor_is_bgr_and_ignores_the_high_byte(self):
        self.assertEqual(theme.tcolor(-14135064), "#E85028")
        self.assertEqual(theme.tcolor(577656), "#78D008")
        self.assertEqual(theme.tcolor(-16777216), "#000000")

    def test_neutral_knobs_keep_the_default_surfaces(self):
        palette = theme.build_palette({"Hue": "0", "Saturation": "0", "Lightness": "0", "Contrast": "0"})
        for key, value in theme.BASE.items():
            self.assertEqual(palette[key], value, key)

    def test_missing_theme_uses_the_default_palette(self):
        self.assertEqual(theme.build_palette(None), theme.DEFAULT_PALETTE)

    def test_full_desaturation_gives_gray_surfaces(self):
        palette = theme.build_palette({"Saturation": "-256"})
        r, g, b = theme.rgb(palette["PANEL"])
        self.assertEqual(r, g)
        self.assertEqual(g, b)

    def test_lightness_knob_direction(self):
        base = theme.luminance(theme.BASE["PANEL"])
        self.assertLess(theme.luminance(theme.build_palette({"Lightness": "-150"})["PANEL"]), base)
        self.assertGreater(theme.luminance(theme.build_palette({"Lightness": "150"})["PANEL"]), base)

    def test_garbage_values_do_not_break_the_palette(self):
        palette = theme.build_palette({"Hue": "abc", "Highlight": "x", "Lightness": "99999"})
        self.assertTrue(all(re.fullmatch(r"#[0-9A-F]{6}", v) for v in palette.values()))

    def test_text_stays_readable_when_a_theme_hides_it(self):
        palette = theme.build_palette({"Lightness": "-200", "TextColor": "0"})
        self.assertGreater(theme.contrast(palette["TEXT"], palette["PANEL"]), 2.5)


class FileTests(unittest.TestCase):
    """Чтение файлов тем."""

    def test_read_theme_with_bom(self):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "t.flstheme")
            with open(path, "w", encoding="utf-8", newline="") as f:
                f.write(SAMPLE)
            values = theme.read_theme(path)
            self.assertEqual(values["Lightness"], "-153")
            self.assertEqual(theme.build_palette(values)["LED"], "#E85028")

    def test_unreadable_or_foreign_file_is_ignored(self):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "other.txt")
            with open(path, "w") as f:
                f.write("just text")
            self.assertIsNone(theme.read_theme(path))
            self.assertIsNone(theme.read_theme(os.path.join(folder, "missing")))

    def test_active_theme_found_next_to_the_database(self):
        with tempfile.TemporaryDirectory() as root:
            db = os.path.join(root, "FL Studio", "Presets", "Plugin database")
            themes = os.path.join(root, "FL Studio", "Settings", "Themes")
            os.makedirs(db)
            os.makedirs(themes)
            current = os.path.join(themes, "__current.flstheme")
            with open(current, "w", encoding="utf-8") as f:
                f.write(SAMPLE)
            original = theme._registry_theme_name
            theme._registry_theme_name = lambda: ""
            try:
                self.assertEqual(theme.find_active_theme(db), current)
            finally:
                theme._registry_theme_name = original


class ImageTests(unittest.TestCase):
    """Создание картинок."""

    def test_generated_images_are_png(self):
        import base64
        led = base64.b64decode(theme.led_image(15, "#E85028", "#73797D"))
        self.assertTrue(led.startswith(b"\x89PNG"))
        tint = base64.b64decode(theme.tint_mask(2, bytes([0, 64, 128, 255]), "#102030"))
        self.assertTrue(tint.startswith(b"\x89PNG"))


class LanguageTests(unittest.TestCase):
    """Файлы языков."""

    def test_every_interface_string_has_an_english_entry(self):
        missing = []
        for name in ("ui.py", "core.py", "settings_page.py", "about.py"):
            with open(os.path.join(SRC, name), encoding="utf-8") as f:
                source = f.read()
            for raw in re.findall(r'tr\("((?:[^"\\]|\\.)*)"\)', source):
                text = re.sub(r"\\(.)", lambda m: {"n": "\n", "\\": "\\"}.get(m.group(1), m.group(1)), raw)
                if text not in i18n.EN:
                    missing.append(text)
        self.assertEqual(missing, [])

    def test_all_twenty_language_files_are_complete(self):
        codes = i18n.available()
        self.assertEqual(len(codes), 20, sorted(codes))
        for code in codes:
            data = i18n._read(code)
            meta = data.pop("_meta")
            self.assertIn(meta["plural"], ("simple", "slavic", "polish"), code)
            self.assertEqual(set(data), set(i18n.EN), code)
            for source, text in data.items():
                self.assertTrue(text.strip(), (code, source))
                self.assertEqual(sorted(re.findall(r"{\w+}", source)), sorted(re.findall(r"{\w+}", text)), (code, source))

    def test_missing_language_and_string_fall_back_to_english(self):
        i18n.set_language("XX-xx")
        self.assertEqual(i18n.LANG, "EN-en")
        self.assertEqual(i18n.tr("Поиск"), "Find")
        i18n.set_language("ZH-cn")
        i18n._table.pop("Поиск", None)
        self.assertEqual(i18n.tr("Поиск"), "Find")
        i18n.set_language("ru")

    def test_polish_plural(self):
        i18n.set_language("PL-pl")
        self.assertTrue(i18n.plural(22, "плагин", "плагина", "плагинов").startswith("22 "))
        self.assertEqual(i18n.plural(21, "плагин", "плагина", "плагинов"), f"21 {i18n.tr('плагинов')}")
        self.assertEqual(i18n.plural(1, "плагин", "плагина", "плагинов"), f"1 {i18n.tr('плагин')}")
        i18n.set_language("ru")

    def test_plural_rules(self):
        i18n.set_language("ru")
        self.assertEqual(i18n.plural(21, "плагин", "плагина", "плагинов"), "21 плагин")
        self.assertEqual(i18n.plural(12, "плагин", "плагина", "плагинов"), "12 плагинов")
        i18n.set_language("en")
        self.assertEqual(i18n.plural(1, "плагин", "плагина", "плагинов"), "1 plugin")
        self.assertEqual(i18n.plural(21, "плагин", "плагина", "плагинов"), "21 plugins")
        i18n.set_language("ru")


if __name__ == "__main__":
    unittest.main()
