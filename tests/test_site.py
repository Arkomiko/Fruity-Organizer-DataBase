"""Тесты сайта: страницы есть на всех языках, внутренние ссылки ведут на существующие файлы, смайликов нет."""
import os
import re
import sys
import tempfile
import unittest
import zipfile

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "tools"))
import gen_site  # noqa: E402

# Значки, стрелки и эмодзи: на сайте их быть не должно.
PICTOGRAMS = re.compile("[←-⇿⌀-➿⬀-⯿\U0001f000-\U0001faff]")


class SiteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.languages = gen_site.main(cls.tmp.name)
        cls.pages = [os.path.join(folder, name) for folder, _dirs, names in os.walk(cls.tmp.name) for name in names if name.endswith(".html")]

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_every_language_has_every_page(self):
        expected = self.languages * (3 + len(gen_site.WIKI)) + 1  # главная, раздел модов, содержание вики и её страницы
        self.assertEqual(len(self.pages), expected)

    def test_mod_archives_exist_and_hold_named_folders(self):
        folder = os.path.join(self.tmp.name, "mods")
        for name, _info in gen_site.mod_folders():
            with zipfile.ZipFile(os.path.join(folder, gen_site.zip_name(name))) as archive:
                self.assertIn(name + "/index.json", archive.namelist())
        with zipfile.ZipFile(os.path.join(folder, gen_site.PACK)) as archive:
            for name, _info in gen_site.mod_folders():
                self.assertIn(name + "/index.json", archive.namelist())

    def test_style_and_script_addresses_carry_a_fingerprint(self):
        for page in self.pages:
            with open(page, encoding="utf-8") as f:
                html = f.read()
            self.assertRegex(html, r'site\.css\?v=[0-9a-f]{10}"', page)
            self.assertRegex(html, r'site\.js\?v=[0-9a-f]{10}"', page)

    def test_internal_links_point_to_real_pages(self):
        for page in self.pages:
            with open(page, encoding="utf-8") as f:
                html = f.read()
            for target in re.findall(r'href="([^"#]+\.html)"', html):
                if not target.startswith("http"):
                    path = os.path.normpath(os.path.join(os.path.dirname(page), target))
                    self.assertTrue(os.path.isfile(path), (page, target))

    def test_no_pictograms(self):
        for page in self.pages:
            with open(page, encoding="utf-8") as f:
                self.assertIsNone(PICTOGRAMS.search(f.read()), page)


if __name__ == "__main__":
    unittest.main()
