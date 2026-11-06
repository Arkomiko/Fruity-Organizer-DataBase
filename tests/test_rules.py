"""Тесты определения назначения, раскладок, запросов фильтра и раскладки по шаблонам."""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import core  # noqa: E402
import i18n  # noqa: E402
import rules  # noqa: E402


def plugin(name="Thing", kind="Effects", category="", vendor="Acme", fmt="VST3", ok=True, organized=None, purposes=None):
    p = core.Plugin(key=f"{kind}\\{fmt}\\{name}", kind=kind, group=fmt, source=f"{kind}\\{fmt}", name=name,
                    files=[core.PluginFile(name, f"C:\\x\\{name}.vst3", fmt, "64", vendor, category)], ok=ok, type_known=True,
                    fst=None, nfo=None)
    p.vendor = vendor
    p.organized_in = organized
    p.purposes, p.purpose_source = (purposes, "test") if purposes else rules.classify(p)
    p.search = f"{p.name} {p.vendor}".casefold()
    return p


class ClassifyTests(unittest.TestCase):
    """Определение назначения плагина."""

    def check(self, expected, **kwargs):
        self.assertEqual(rules.classify(plugin(**kwargs))[0][0], expected, kwargs)

    def test_vst3_category_is_used(self):
        self.check("reverb", name="Mystery", category="Fx|Reverb")
        self.check("delay", name="Mystery", category="Delay")
        self.check("restoration", name="Mystery", category="Fx|Restoration")

    def test_generic_category_falls_through_to_name_words(self):
        self.check("delay", name="kHs Dual Delay", category="Fx")
        self.check("dynamics", name="kHs Compressor", category="Effect")
        self.check("eq", name="Fruity Parametric EQ 2")
        self.check("modulation", name="Vintage Chorus")

    def test_known_names_beat_categories_and_longest_entry_wins(self):
        self.check("dynamics", name="OTT", category="Fx")
        self.check("reverb", name="ValhallaPlate", category="Effect")
        self.check("modulation", name="ValhallaUberMod", category="Effect")
        self.check("synth", name="Serum", kind="Generators", category="Synth")
        self.check("creative", name="SerumFX", category="Effect")

    def test_generators_never_get_effect_purposes_from_words(self):
        self.check("drums", name="Fruit Kick", kind="Generators")
        self.check("synth", name="Reverb Pad Machine", kind="Generators")

    def test_fallbacks(self):
        self.check("other", name="Zzyzx")
        self.check("synth", name="Zzyzx", kind="Generators")

    def test_multi_job_plugin_is_creative_and_keeps_tags(self):
        purposes, _ = rules.classify(plugin(name="Mystery", category="Fx|Delay|Distortion|Dynamics"))
        self.assertEqual(purposes[0], "creative")
        self.assertIn("delay", purposes)

    def test_priority_manual_then_rule_then_automatic(self):
        p = plugin(name="OTT", category="Fx")
        rule = rules.Rule("mastering", name="^ott$")
        self.assertEqual(rules.classify(p, {}, [rule]), (["mastering"], "rule"))
        self.assertEqual(rules.classify(p, {p.name_id: "utility"}, [rule]), (["utility"], "manual"))

    def test_rules_by_vendor_kind_and_broken_pattern(self):
        p = plugin(name="Anything", vendor="Klevgrand")
        self.assertEqual(rules.classify(p, {}, [rules.Rule("drums", vendor="klev")])[0], ["drums"])
        self.assertNotEqual(rules.classify(p, {}, [rules.Rule("drums", vendor="klev", kind="Generators")])[0], ["drums"])
        self.assertEqual(rules.classify(p, {}, [rules.Rule("drums", name="(")])[0], ["other"])

    def test_load_rules_ignores_bad_entries(self):
        loaded = rules.load_rules([{"purpose": "eq", "name": "x"}, {"purpose": "nope"}, "junk"])
        self.assertEqual([r.purpose for r in loaded], ["eq"])


class LayoutTests(unittest.TestCase):
    """Шаблоны папок."""

    def setUp(self):
        i18n.set_language("en")
        self.addCleanup(i18n.set_language, "ru")
        self.p = plugin(name="Reverb One", category="Fx|Reverb", vendor="Acme")

    def test_both_nesting_orders(self):
        self.assertEqual(rules.layout_parts(rules.LAYOUTS["vendor_purpose"], self.p), ["Acme", i18n.tr("Реверберация")])
        self.assertEqual(rules.layout_parts(rules.LAYOUTS["purpose_vendor"], self.p), [i18n.tr("Реверберация"), "Acme"])

    def test_custom_template_with_text_tokens_and_slashes(self):
        self.assertEqual(rules.layout_parts("My/{format}-{bits}\\{letter}", self.p), ["My", "VST3-64", "R"])

    def test_template_validation(self):
        self.assertEqual(rules.layout_tokens("{vendor}\\{purpose}"), {})
        self.assertIn("unknown", rules.layout_tokens("{nope}"))
        self.assertIn("empty", rules.layout_tokens(" \\ "))

    def test_empty_values_drop_the_level(self):
        self.p.vendor = ""
        self.assertEqual(rules.layout_parts("{vendor}\\{purpose}", self.p), [i18n.tr("Реверберация")])

    def test_letters(self):
        self.assertEqual(rules._first_letter("8-Bit Shaper"), "0-9")
        self.assertEqual(rules._first_letter("ёлка"), "Ё")


class QueryTests(unittest.TestCase):
    """Запросы и фильтры."""

    def setUp(self):
        self.items = [
            plugin(name="Hall Verb", category="Fx|Reverb", vendor="Plugin Alliance"),
            plugin(name="Tape Delay", category="Fx|Delay", vendor="Klevgrand", fmt="VST"),
            plugin(name="Big Synth", kind="Generators", category="Synth", vendor="Klevgrand", organized="C:\\x"),
            plugin(name="Broken", ok=False, vendor="Other"),
        ]

    def names(self, text, selections=None):
        q = rules.parse_query(text)
        return [p.name for p in self.items if q.matches(p, selections)]

    def test_plain_words_all_must_match(self):
        self.assertEqual(self.names("tape klev"), ["Tape Delay"])
        self.assertEqual(self.names("-klev"), ["Hall Verb", "Broken"])

    def test_fields_lists_negation_quotes(self):
        self.assertEqual(self.names("purpose:reverb,delay"), ["Hall Verb", "Tape Delay"])
        self.assertEqual(self.names('vendor:"plugin alliance"'), ["Hall Verb"])
        self.assertEqual(self.names("-format:vst3"), ["Tape Delay"])
        self.assertEqual(self.names("-format:vst"), ["Hall Verb", "Big Synth", "Broken"])
        self.assertEqual(self.names("format:vst"), ["Tape Delay"])
        self.assertEqual(self.names("kind:synth"), ["Big Synth"])
        self.assertEqual(self.names("status:error"), ["Broken"])
        self.assertEqual(self.names("organized:yes vendor:klev"), ["Big Synth"])

    def test_russian_field_names_and_values(self):
        self.assertEqual(self.names("производитель:klev организован:нет"), ["Tape Delay"])
        self.assertEqual(self.names("назначение:реверб"), ["Hall Verb"])
        self.assertEqual(self.names("тип:синт"), ["Big Synth"])

    def test_unknown_field_is_treated_as_text(self):
        self.assertEqual(self.names("nosuch:thing"), [])

    def test_menu_selections_combine(self):
        self.assertEqual(self.names("", {"vendor": ["Klevgrand"], "kind": ["Effects"]}), ["Tape Delay"])
        self.assertEqual(self.names("", {"purpose": ["reverb", "delay"]}), ["Hall Verb", "Tape Delay"])

    def test_facet_counts_ignore_their_own_group(self):
        q = rules.parse_query("")
        counts = rules.facet_counts(self.items, "vendor", q, {"vendor": ["Other"], "kind": ["Effects"]})
        self.assertEqual(counts, {"Plugin Alliance": 1, "Klevgrand": 1, "Other": 1})

    def test_every_field_runs_on_a_bare_plugin(self):
        p = core.Plugin("k", "Effects", "VST", "s", "n", [], False, False, None, None)
        for name, getter in rules.FIELDS.items():
            self.assertIsNotNone(getter(p), name)


class DateTests(unittest.TestCase):
    """Дата файла плагина."""

    def test_delphi_date_decoding(self):
        self.assertEqual(core._delphi_date("not a number"), 0.0)
        stamp = core._delphi_date("4676582957090078720")
        self.assertTrue(1_600_000_000 < stamp < 2_000_000_000, stamp)


class PlanTests(unittest.TestCase):
    """План раскладки по шаблонам."""

    def setUp(self):
        i18n.set_language("en")
        self.addCleanup(i18n.set_language, "ru")
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = os.path.join(self.tmp.name, "db")
        self.source = os.path.join(self.db, "Installed", "Effects", "VST3")
        os.makedirs(self.source)
        self.items = [self._make("Hall Verb", "Fx|Reverb", "Acme"), self._make("Tape Delay", "Fx|Delay", "Acme")]

    def _make(self, name, category, vendor):
        p = plugin(name=name, category=category, vendor=vendor)
        p.fst = os.path.join(self.source, name + ".fst")
        p.nfo = os.path.join(self.source, name + ".nfo")
        for path in (p.fst, p.nfo):
            with open(path, "w") as f:
                f.write(name)
        p.purposes, p.purpose_source = rules.classify(p)
        return p

    def exists(self, *parts):
        return os.path.isfile(os.path.join(self.db, *parts))

    def run_layout(self, key, **kw):
        opts = core.Options(layout=rules.LAYOUTS[key], **kw)
        plan = core.build_plan(self.items, self.db, opts, {})
        return plan, core.execute(plan, self.db, opts), opts

    def test_vendor_then_purpose(self):
        self.run_layout("vendor_purpose")
        self.assertTrue(self.exists("Effects", "Acme", i18n.tr("Реверберация"), "Hall Verb.fst"))
        self.assertTrue(self.exists("Effects", "Acme", i18n.tr("Дилеи"), "Tape Delay.nfo"))

    def test_purpose_then_vendor(self):
        self.run_layout("purpose_vendor")
        self.assertTrue(self.exists("Effects", i18n.tr("Реверберация"), "Acme", "Hall Verb.fst"))

    def test_plan_lists_relative_folders(self):
        plan, _, _ = self.run_layout("purpose")
        self.assertEqual(plan.folders(self.db), {os.path.join("Effects", i18n.tr("Дилеи")): 1, os.path.join("Effects", i18n.tr("Реверберация")): 1})

    def test_reorganize_moves_existing_copies_and_undo_restores_them(self):
        self.run_layout("vendor")
        organized, folders = core.scan_organized(self.db)
        for p in self.items:
            p.organized_in = organized[(p.kind, p.name_id)]
        opts = core.Options(layout=rules.LAYOUTS["purpose_vendor"], reorganize=True)
        plan = core.build_plan(self.items, self.db, opts, folders)
        self.assertEqual(plan.moves, 2)
        result = core.execute(plan, self.db, opts)
        self.assertEqual(result.moved, 2)
        self.assertTrue(self.exists("Effects", i18n.tr("Реверберация"), "Acme", "Hall Verb.fst"))
        self.assertTrue(self.exists("Effects", i18n.tr("Реверберация"), "Acme", "Hall Verb.nfo"))
        self.assertFalse(os.path.exists(os.path.join(self.db, "Effects", "Acme")))
        self.assertTrue(os.path.isfile(self.items[0].fst))
        journal = os.path.join(self.tmp.name, "undo.json")
        core.write_journal(journal, self.db, result)
        core.undo(journal, self.db, trash=lambda paths: True)
        self.assertTrue(self.exists("Effects", "Acme", "Hall Verb.fst"))
        self.assertFalse(os.path.exists(os.path.join(self.db, "Effects", i18n.tr("Реверберация"))))

    def test_reorganize_skips_what_is_already_right_and_never_overwrites(self):
        self.run_layout("vendor")
        organized, folders = core.scan_organized(self.db)
        for p in self.items:
            p.organized_in = organized[(p.kind, p.name_id)]
        plan = core.build_plan(self.items, self.db, core.Options(layout="{vendor}", reorganize=True), folders)
        self.assertEqual((len(plan.actions), plan.skipped.get("in_place")), (0, 2))
        clash = os.path.join(self.db, "Effects", i18n.tr("Дилеи"))
        os.makedirs(clash)
        with open(os.path.join(clash, "Tape Delay.fst"), "w") as f:
            f.write("mine")
        opts = core.Options(layout="{purpose}", reorganize=True)
        result = core.execute(core.build_plan(self.items, self.db, opts, folders), self.db, opts)
        self.assertEqual(len(result.errors), 1)
        with open(os.path.join(clash, "Tape Delay.fst")) as f:
            self.assertEqual(f.read(), "mine")

    def test_unsafe_template_text_stays_inside_the_database(self):
        p = self.items[0]
        p.vendor = "..\\..\\evil"
        dest = core.target_folder(self.db, p, core.Options(layout="..\\{vendor}\\.."), {})
        self.assertTrue(dest.startswith(os.path.join(self.db, "Effects") + os.sep))
        self.assertNotIn("..", dest[len(self.db):])


if __name__ == "__main__":
    unittest.main()
