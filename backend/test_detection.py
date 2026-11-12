"""Detection tests, no microphone needed: python -m unittest test_detection

Phonetic tests require espeak-ng (see phonetics.py).
"""

import unittest

from detection import Detector, Rule
from phonetics import create_phonemizer

phonemizer = create_phonemizer()


def triggers(rule: Rule, sentence: str) -> bool:
    return bool(Detector([rule], phonemizer).matches(sentence))


class TestPhonetic(unittest.TestCase):
    def test_epoux(self):
        r = Rule("w1", "époux")
        should = ["époux", "bah des poux", "les poux", "c'est des poux", "mes époux", "et pou"]
        never = ["dépourvu", "des pouces", "épouse", "c'est pourri", "depuis", "bonjour"]
        for s in should:
            self.assertTrue(triggers(r, s), s)
        for s in never:
            self.assertFalse(triggers(r, s), s)

    def test_without_word_end(self):
        r = Rule("w1", "époux", word_end=False)
        self.assertTrue(triggers(r, "dépourvu"))

    def test_word_start(self):
        r = Rule("w1", "époux", word_start=True)
        self.assertTrue(triggers(r, "les époux"))
        self.assertFalse(triggers(r, "des poux"))

    def test_expression(self):
        r = Rule("w1", "en vrai")
        self.assertTrue(triggers(r, "mais en vrai c'est bien"))
        self.assertFalse(triggers(r, "le vrai problème"))


class TestExact(unittest.TestCase):
    def test_word(self):
        r = Rule("w1", "époux", mode="exact")
        self.assertTrue(triggers(r, "mon EPOUX"))
        self.assertFalse(triggers(r, "bah des poux"))

    def test_plural(self):
        r = Rule("w1", "genre", mode="exact")
        self.assertTrue(triggers(r, "des genres"))
        r.plural = False
        self.assertFalse(triggers(r, "des genres"))


class TestAnalyze(unittest.TestCase):
    def test_single_trigger_per_utterance(self):
        d = Detector([Rule("w1", "époux", cooldown=0)], phonemizer)
        self.assertEqual(len(d.analyze("bah des poux", final=False)), 1)
        self.assertEqual(len(d.analyze("bah des poux quoi", final=False)), 0)
        self.assertEqual(len(d.analyze("bah des poux quoi", final=True)), 0)
        self.assertEqual(len(d.analyze("des poux", final=True)), 1)

    def test_cooldown(self):
        d = Detector([Rule("w1", "époux", cooldown=60)], phonemizer)
        self.assertEqual(len(d.analyze("époux", final=True)), 1)
        self.assertEqual(len(d.analyze("époux", final=True)), 0)

    def test_live_update(self):
        d = Detector([Rule("w1", "époux")], phonemizer)
        d.update([Rule("w2", "bref")])
        self.assertEqual([r.id for r in d.matches("bref des poux")], ["w2"])


if __name__ == "__main__":
    unittest.main()
