"""Tests of the "add_word" punishment's logic: python -m unittest test_words

No microphone and no espeak needed.
"""

import random
import tempfile
import unittest
from pathlib import Path

from config import AddWordSettings, Config, ConfigStore, PunishmentSelection, Word
from detection import Detector, Rule
from words import build_word, candidates, pick_word


def word(text: str, **kwargs) -> Word:
    return Word(id=f"w-{text}", word=text, **kwargs)


class TestPick(unittest.TestCase):
    def test_skips_active_words_ignoring_case_and_accents(self):
        words = [word("époux"), word("Genre")]
        self.assertEqual(candidates(["epoux", "GENRE", "voiture"], words), ["voiture"])

    def test_disabled_word_does_not_block(self):
        self.assertEqual(candidates(["époux"], [word("époux", enabled=False)]), ["époux"])

    def test_ignores_empty_and_duplicates(self):
        self.assertEqual(candidates(["", "  ", "???", "chat", "Chat", " chat "], []), ["chat"])

    def test_nothing_left(self):
        self.assertIsNone(pick_word(["a", "b"], [word("a"), word("b")]))
        self.assertIsNone(pick_word([], []))

    def test_random_but_only_from_candidates(self):
        seen = {pick_word(["a", "b", "c"], [word("a")], rng=random.Random(i)) for i in range(40)}
        self.assertEqual(seen, {"b", "c"})

    def test_accept_filter(self):
        self.assertEqual(pick_word(["bad", "good"], [], accept=lambda t: t == "good"), "good")
        self.assertIsNone(pick_word(["bad"], [], accept=lambda t: False))


class TestBuild(unittest.TestCase):
    def test_copies_the_triggering_words_punishments(self):
        trigger = word("a", punishments=PunishmentSelection(strategy="random", ids=["p1", "p2"]))
        settings = AddWordSettings(punishments=PunishmentSelection(ids=["other"]))
        new = build_word("b", settings, trigger, now=100, word_id="w-new")
        self.assertEqual((new.punishments.strategy, new.punishments.ids), ("random", ["p1", "p2"]))
        trigger.punishments.ids.append("p3")  # a copy, not a shared list
        self.assertEqual(new.punishments.ids, ["p1", "p2"])

    def test_own_list(self):
        trigger = word("a", punishments=PunishmentSelection(ids=["p1"]))
        settings = AddWordSettings(punishments_from="list", punishments=PunishmentSelection(ids=["own"]))
        self.assertEqual(build_word("b", settings, trigger, 0, "w").punishments.ids, ["own"])

    def test_own_list_without_trigger(self):  # testing the punishment from the panel
        settings = AddWordSettings(punishments=PunishmentSelection(ids=["own"]))
        self.assertEqual(build_word("b", settings, None, 0, "w").punishments.ids, ["own"])

    def test_lifetime(self):
        permanent = build_word("b", AddWordSettings(), None, 100, "w")
        self.assertTrue(permanent.auto)
        self.assertIsNone(permanent.expires_at)
        self.assertEqual(build_word("b", AddWordSettings(duration=30), None, 100, "w").expires_at, 130)

    def test_mode_and_display(self):
        new = build_word("b", AddWordSettings(mode="exact", display_mode="hidden"), None, 0, "w")
        self.assertEqual((new.mode, new.display_mode), ("exact", "hidden"))


class TestStore(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.store = ConfigStore(Path(self.dir.name) / "config.json")
        self.store.replace(Config(words=[word("keep")]))

    def tearDown(self):
        self.dir.cleanup()

    def test_expiry(self):
        self.store.add_word(word("temp", auto=True, expires_at=100))
        self.store.add_word(word("later", auto=True, expires_at=200))
        self.assertEqual(self.store.expire_words(50), [])
        self.assertEqual([w.word for w in self.store.expire_words(150)], ["temp"])
        self.assertEqual([w.word for w in self.store.read().words], ["keep", "later"])

    def test_a_stale_panel_cannot_resurrect_an_expired_word(self):
        self.store.add_word(word("temp", auto=True, expires_at=100))
        stale = self.store.read()  # the panel's copy, still holding "temp"
        self.store.expire_words(150)
        self.store.replace(stale)
        self.assertEqual([w.word for w in self.store.read().words], ["keep"])

    def test_the_panel_cannot_change_the_lifetime(self):
        self.store.add_word(word("temp", auto=True, expires_at=100))
        edited = self.store.read()
        for w in edited.words:
            w.expires_at, w.auto = None, False
        self.store.replace(edited)
        temp = next(w for w in self.store.read().words if w.word == "temp")
        self.assertEqual((temp.auto, temp.expires_at), (True, 100))

    def test_the_panel_can_delete_an_auto_word(self):
        self.store.add_word(word("temp", auto=True))
        edited = self.store.read()
        edited.words = [w for w in edited.words if w.word != "temp"]
        self.store.replace(edited)
        self.assertEqual([w.word for w in self.store.read().words], ["keep"])

    def test_counters_are_kept(self):
        self.store.increment("w-keep")
        edited = self.store.read()
        edited.words[0].count = 0
        self.assertEqual(self.store.replace(edited).words[0].count, 1)


class TestDetectorReload(unittest.TestCase):
    def test_reload_keeps_the_cooldown(self):
        d = Detector([Rule("w1", "chat", mode="exact", cooldown=60)])
        self.assertEqual(len(d.analyze("un chat", final=True)), 1)
        d.update([Rule("w1", "chat", mode="exact", cooldown=60), Rule("w2", "chien", mode="exact")])
        self.assertEqual(len(d.analyze("un chat", final=True)), 0)  # still cooling down
        self.assertEqual(len(d.analyze("un chien", final=True)), 1)  # the new word works at once

    def test_can_compile(self):
        d = Detector([])
        self.assertTrue(d.can_compile(Rule("x", "chat", mode="exact")))
        self.assertFalse(d.can_compile(Rule("x", "chat", mode="unknown")))


if __name__ == "__main__":
    unittest.main()
