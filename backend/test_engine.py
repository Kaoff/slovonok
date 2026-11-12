"""Engine tests (learning mode, dry run, phonemize): python -m unittest test_engine

Needs espeak-ng and the vosk package (imported by the engine), but no microphone and no model:
the engine is created without listening.
"""

import tempfile
import threading
import time
import unittest
from pathlib import Path

from config import Config, ConfigStore, Word
from detection import Rule
from engine import Engine


class TestLearningMode(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        store = ConfigStore(Path(self.dir.name) / "config.json")
        store.replace(Config(words=[Word(id="w1", word="Pakwaf", tolerance=1)], cooldown=0))
        self.engine = Engine(store, listening_enabled=False)
        # on_text ignores any thread but the listener's: pretend this one is it
        self.engine.listener = threading.current_thread()
        self.published = []
        self.engine.broadcaster.publish = self.published.append

    def tearDown(self):
        self.dir.cleanup()

    def count(self) -> int:
        return self.engine.store.read().words[0].count

    def test_detects_normally(self):
        self.engine.on_text("pas quoi", True)  # tolerance 1: the final f is lost
        self.assertEqual(self.count(), 1)

    def test_learning_shows_speech_but_does_not_detect(self):
        self.engine.set_learning(True)
        self.assertTrue(self.engine.learning)
        self.engine.on_text("pas quoi", True)
        self.assertEqual(self.count(), 0)
        self.assertEqual([e["text"] for e in self.published if e["type"] == "transcription"], ["pas quoi"])
        self.assertFalse(any(e["type"] == "detection" for e in self.published))

    def test_learning_ends_on_request(self):
        self.engine.set_learning(True)
        self.engine.set_learning(False)
        self.engine.on_text("pas quoi", True)
        self.assertEqual(self.count(), 1)

    def test_learning_ends_by_itself_if_the_panel_disappears(self):
        self.engine.set_learning(True)
        self.engine._learning_until = time.monotonic() - 1  # no news from the panel for a while
        self.assertFalse(self.engine.learning)
        self.engine.on_text("pas quoi", True)
        self.assertEqual(self.count(), 1)


class TestDryRun(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        store = ConfigStore(Path(self.dir.name) / "config.json")
        store.replace(Config(words=[Word(id="w1", word="Pakwaf")]))
        self.engine = Engine(store, listening_enabled=False)

    def tearDown(self):
        self.dir.cleanup()

    def test_tells_what_would_match_without_punishing(self):
        rule = Rule("dry", "Pakwaf", variants=["pas voir"], tolerance=1)
        result = self.engine.dry_run(rule, ["pas voir", "pas quoi", "bonjour", "  ", ""])
        self.assertEqual(result, [True, True, False, False, False])
        self.assertEqual(self.engine.store.read().words[0].count, 0)

    def test_an_unusable_word_is_refused(self):
        with self.assertRaises(ValueError):
            self.engine.dry_run(Rule("dry", "???"), ["bonjour"])

    def test_phonemize(self):
        sounds = self.engine.phonemize(["Pakwaf", "pas quoi", ""])
        self.assertEqual(sounds[0], "pakwaf")
        self.assertEqual(sounds[1], "pa kwa")
        self.assertEqual(sounds[2], "")


if __name__ == "__main__":
    unittest.main()
