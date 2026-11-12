"""Approximate matching of sounds: python -m unittest test_fuzzy (no espeak needed)."""

import unittest

from fuzzy import approximate_match, effective_tolerance


def sounds(text: str) -> tuple[list[str], list[bool]]:
    """"p a . k w a" style: one letter = one sound, "/" separates words."""
    segs, starts = [], []
    for word in text.split("/"):
        letters = word.split()
        segs += letters
        starts += [True] + [False] * (len(letters) - 1)
    return segs, starts


def match(target: str, text: str, edits: int, **options) -> bool:
    return approximate_match(target.split(), *sounds(text), edits, **options)


class TestApproximate(unittest.TestCase):
    TARGET = "p a k w a f"

    def test_exact(self):
        self.assertTrue(match(self.TARGET, "p a k w a f", 0))
        self.assertFalse(match(self.TARGET, "p a k w a", 0))

    def test_word_boundaries_cost_nothing(self):
        self.assertTrue(match(self.TARGET, "p a / k w a / f", 0))

    def test_one_missing_sound(self):  # "pas quoi" for "pakwaf": the final f is lost
        self.assertFalse(match(self.TARGET, "p a / k w a", 0))
        self.assertTrue(match(self.TARGET, "p a / k w a", 1))

    def test_one_extra_sound_and_one_missing(self):  # "par quoi"
        self.assertFalse(match(self.TARGET, "p a r / k w a", 1))
        self.assertTrue(match(self.TARGET, "p a r / k w a", 2))

    def test_two_substitutions(self):  # "pas voir"
        self.assertFalse(match(self.TARGET, "p a / v w a r", 1))
        self.assertTrue(match(self.TARGET, "p a / v w a r", 2))

    def test_found_inside_a_longer_text(self):
        self.assertTrue(match(self.TARGET, "s a l y / t u / s e / p a / k w a", 1))
        self.assertFalse(match(self.TARGET, "s a l y / t u / l ø / m õ d", 2))

    def test_word_end(self):
        # "p a k w a f" found at the start of a longer word: accepted only without word_end
        self.assertTrue(match(self.TARGET, "p a k w a f i", 0, word_end=False))
        self.assertFalse(match(self.TARGET, "p a k w a f i", 0, word_end=True))
        self.assertTrue(match(self.TARGET, "p a k w a f / i", 0, word_end=True))

    def test_word_start(self):
        self.assertTrue(match(self.TARGET, "d p a k w a f", 0, word_start=False))
        self.assertFalse(match(self.TARGET, "d p a k w a f", 0, word_start=True))
        self.assertTrue(match(self.TARGET, "d / p a k w a f", 0, word_start=True))

    def test_empty(self):
        self.assertFalse(approximate_match([], ["a"], [True], 1))
        self.assertFalse(match(self.TARGET, "", 2))


class TestEffectiveTolerance(unittest.TestCase):
    def test_short_words_get_less(self):
        self.assertEqual(effective_tolerance(6, 2), 2)
        self.assertEqual(effective_tolerance(5, 2), 1)
        self.assertEqual(effective_tolerance(4, 2), 0)
        self.assertEqual(effective_tolerance(3, 2), 0)

    def test_never_more_than_asked(self):
        self.assertEqual(effective_tolerance(12, 1), 1)
        self.assertEqual(effective_tolerance(12, 0), 0)


if __name__ == "__main__":
    unittest.main()
