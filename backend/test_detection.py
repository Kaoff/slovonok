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


# What Vosk small-fr actually made of an invented word (synthetic speech, see the OOV probe)
PAKWAF_HEARD = ["pas voir", "pas quoi", "voir", "salut tout le monde sait par quoi", "j'adore parc wars"]


class TestPhonemizer(unittest.TestCase):
    def test_no_language_flags_in_sounds(self):
        # espeak marks foreign words "(en)…(fr)": those flags must never reach the detector
        for ipa in phonemizer(["wars", "live", "parc"]):
            self.assertNotIn("(", ipa)
            self.assertNotIn(")", ipa)

    def test_english_word_is_detectable(self):
        self.assertTrue(triggers(Rule("w1", "live"), "on est en live"))


class TestVariants(unittest.TestCase):
    def test_exact_mode_variant(self):
        r = Rule("w1", "Pakwaf", mode="exact", variants=["pas quoi"])
        self.assertTrue(triggers(r, "je dis pas quoi"))
        self.assertTrue(triggers(r, "Pakwaf"))
        self.assertFalse(triggers(r, "par quoi"))

    def test_phonetic_variant(self):
        r = Rule("w1", "Pakwaf", variants=["pas voir"])
        self.assertTrue(triggers(r, "il dit pas voir"))
        self.assertTrue(triggers(r, "il dit pa voir"))  # same sounds as the variant
        self.assertFalse(triggers(r, "il dit pas vu"))

    def test_variant_uses_the_words_options(self):
        r = Rule("w1", "Pakwaf", variants=["pas quoi"], word_start=True)
        self.assertTrue(triggers(r, "tu dis pas quoi"))
        self.assertFalse(triggers(r, "tu dis impasquoi"))

    def test_one_trigger_and_one_cooldown_for_all_variants(self):
        d = Detector([Rule("w1", "Pakwaf", variants=["pas voir", "pas quoi"], cooldown=60)], phonemizer)
        self.assertEqual(len(d.matches("pas voir pas quoi")), 1)
        self.assertEqual(len(d.analyze("pas voir", final=True)), 1)
        self.assertEqual(len(d.analyze("pas quoi", final=True)), 0)  # another variant, same cooldown

    def test_a_bad_variant_does_not_break_the_rule(self):
        r = Rule("w1", "époux", variants=["???", "", "des poux"])
        d = Detector([r, Rule("w2", "bref")], phonemizer)
        self.assertTrue(d.matches("des poux"))
        self.assertEqual({x.id for x in d.matches("des poux, bref")}, {"w1", "w2"})

    def test_a_bad_word_is_still_refused(self):
        self.assertFalse(Detector([], phonemizer).can_compile(Rule("w1", "???")))
        self.assertFalse(Detector([], phonemizer).can_compile(Rule("w1", "???", mode="exact")))


class TestTolerance(unittest.TestCase):
    def test_default_is_exact(self):
        self.assertFalse(triggers(Rule("w1", "Pakwaf"), "pas quoi"))

    def test_invented_word_heard_as_french(self):
        one = Rule("w1", "Pakwaf", tolerance=1)
        two = Rule("w1", "Pakwaf", tolerance=2)
        self.assertTrue(triggers(one, "pas quoi"))  # the final f is lost
        self.assertFalse(triggers(one, "pas voir"))
        self.assertTrue(triggers(two, "pas voir"))
        self.assertTrue(triggers(two, "salut tout le monde sait par quoi"))
        self.assertFalse(triggers(two, "salut tout le monde"))

    def test_a_close_real_word_matches_too(self):
        # The price of tolerance: "quoique" is one sound away from "quoi" + "f" (see the UI warning)
        self.assertTrue(triggers(Rule("w1", "Pakwaf", tolerance=1), "pas quoique"))
        self.assertFalse(triggers(Rule("w1", "Pakwaf", tolerance=1), "il est parti"))

    def test_short_words_are_protected(self):
        # "bref" has 4 sounds: tolerance can't apply, or "bref" would match half the language
        self.assertFalse(triggers(Rule("w1", "bref", tolerance=2), "brave"))

    def test_applies_to_variants_too(self):
        r = Rule("w1", "Pakwaf", variants=["pas voir"], tolerance=1)
        self.assertTrue(triggers(r, "pas voir"))
        self.assertTrue(triggers(r, "pas voire"))

    def test_the_probe_transcripts(self):
        fuzzy = Rule("w1", "Pakwaf", tolerance=2)
        learned = Rule("w1", "Pakwaf", variants=["voir", "j'adore parc wars"])
        too_far = {"voir", "j'adore parc wars"}  # 3+ sounds away: tolerance can't, a variant can
        for heard in PAKWAF_HEARD:
            self.assertEqual(triggers(fuzzy, heard), heard not in too_far, f"tolerance 2: {heard!r}")
        for heard in too_far:
            self.assertTrue(triggers(learned, heard), f"learned: {heard!r}")
        self.assertFalse(triggers(Rule("w1", "Pakwaf"), "pas voir"))  # exact sounds alone fail


if __name__ == "__main__":
    unittest.main()
