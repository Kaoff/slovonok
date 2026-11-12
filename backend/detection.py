"""Forbidden word detection in a transcript.

Two modes per rule:
- "phonetic": compares sounds, ignoring word boundaries.
  "bah des poux" (/ba de pu/) triggers "époux" (/epu/).
- "exact": compares normalized text (lowercase, no accents).

This module does not depend on Vosk: give it text, it returns the triggered rules.
"""

from __future__ import annotations

import re
import time
import unicodedata
from dataclasses import dataclass, field
from typing import Callable, Iterable

from fuzzy import approximate_match, effective_tolerance

# Phonemizer: list of words -> list of IPA transcriptions (same order).
Phonemizer = Callable[[list[str]], list[str]]

# Close sounds that Vosk and espeak easily confuse: they are merged
# on both sides for more tolerance ("des" /de/ vs /dɛ/, etc.).
EQUIVALENCES = str.maketrans({
    "ɛ": "e",
    "ɔ": "o",
    "ɑ": "a",
    "œ": "ø",
    "ə": "ø",
    "ɐ": "a",
})
# Stress marks, length marks, and any punctuation espeak may output.
TO_REMOVE = re.compile(r"[ˈˌːˑ\-_.,!?;:]")


def normalize_text(text: str) -> str:
    """Lowercase, no accents, apostrophes and hyphens replaced with spaces."""
    text = unicodedata.normalize("NFD", text.lower())
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return text.strip()


def words_to_phonemize(text: str) -> list[str]:
    """Splits into words, keeping accents and apostrophes: espeak needs them
    to pronounce correctly ("dépourvu" ≠ "depourvu", "c'est" ≠ "c est")."""
    return re.findall(r"[\w']+", text.lower().replace("’", "'"))


def normalize_phonemes(ipa: str) -> str:
    """Makes an IPA transcription more tolerant (see EQUIVALENCES)."""
    ipa = unicodedata.normalize("NFD", ipa)
    ipa = TO_REMOVE.sub("", ipa).translate(EQUIVALENCES)
    return re.sub(r"\s+", " ", ipa).strip()


def phoneme_stream(ipa: str) -> tuple[list[str], list[bool]]:
    """The sounds of a phonemized text (words separated by spaces), and for each sound whether
    it starts a word."""
    sounds: list[str] = []
    starts: list[bool] = []
    for word in ipa.split():
        word_sounds = segments(word)
        sounds += word_sounds
        starts += [True] + [False] * (len(word_sounds) - 1)
    return sounds, starts


def segments(ipa: str) -> list[str]:
    """Splits into sounds, keeping diacritics (e.g. nasal ɑ̃) attached to their letter."""
    sounds: list[str] = []
    for c in ipa:
        if unicodedata.combining(c) and sounds:
            sounds[-1] += c
        elif not c.isspace():
            sounds.append(c)
    return sounds


@dataclass
class Rule:
    id: str
    word: str
    mode: str = "phonetic"  # "phonetic" or "exact"
    word_start: bool = False  # the sound must start a word (avoids "crépu" for "époux")
    word_end: bool = True  # the sound must end a word (avoids "dépourvu" for "époux")
    plural: bool = True  # exact mode: also accepts "mots", "chevaux"…
    cooldown: float = 5.0  # seconds between two triggers
    # What Vosk was heard saying for this word ("sounds like"): each one also triggers the rule,
    # with the same options. One rule, several patterns: a single cooldown, a single trigger.
    variants: list[str] = field(default_factory=list)
    # Phonetic mode: sound edits allowed (0 = exact sounds). See fuzzy.py.
    tolerance: int = 0
    _compiled: "Compiled | None" = field(default=None, repr=False)
    _last: float = field(default=0.0, repr=False)


@dataclass
class Compiled:
    patterns: list[re.Pattern]  # exact comparison (regex), one per word or variant
    sounds: list[list[str]]  # phonetic mode: the sounds of each, for approximate matching


class Detector:
    def __init__(
        self,
        rules: Iterable[Rule],
        phonemizer: Phonemizer | None = None,
        cache: dict[str, str] | None = None,
    ):
        self.phonemizer = phonemizer
        self._cache: dict[str, str] = {} if cache is None else cache  # word -> sounds, can be shared
        self._seen_in_utterance: set[str] = set()
        self.rules: list[Rule] = []
        self.update(rules)

    # --- Configuration -------------------------------------------------

    def update(self, rules: Iterable[Rule]) -> None:
        """Replaces the rules (can be called live, e.g. when a punishment adds a word)."""
        rules = list(rules)
        if any(r.mode == "phonetic" for r in rules) and not self.phonemizer:
            raise ValueError("A phonetic rule requires a phonemizer")
        previous = {r.id: r._last for r in self.rules}
        for r in rules:
            r._compiled = self._compile_rule(r)
            r._last = previous.get(r.id, 0.0)  # a reload must not reset the cooldowns
        self.rules = rules

    def can_compile(self, r: Rule) -> bool:
        """False if the rule cannot be used (e.g. a word with no pronounceable sound)."""
        try:
            self._compile_rule(r)
        except ValueError:
            return False
        return True

    def _compile_rule(self, r: Rule) -> Compiled:
        """The word must be usable (else ValueError); an unusable variant is just skipped,
        so one bad variant never takes the detection of every word down."""
        compiled = Compiled([], [])
        for index, text in enumerate([r.word, *r.variants]):
            try:
                pattern, sounds = self._compile_text(r, text)
            except ValueError:
                if index == 0:
                    raise
                continue
            compiled.patterns.append(pattern)
            compiled.sounds.append(sounds)
        return compiled

    def _compile_text(self, r: Rule, text: str) -> tuple[re.Pattern, list[str]]:
        if r.mode == "exact":
            words = normalize_text(text).split()
            if not words:
                raise ValueError(f"Nothing to detect in '{text}'")
            body = r"\s+".join(re.escape(w) for w in words)
            suffix = r"(?:s|x)?" if r.plural else ""
            return re.compile(rf"(?<![a-z0-9]){body}{suffix}(?![a-z0-9])"), []

        if r.mode == "phonetic":
            sounds = segments(self.phonemize_text(text))
            if not sounds:
                raise ValueError(f"Cannot phonemize '{text}'")
            # A word boundary (space) is allowed between every sound.
            body = " ?".join(re.escape(s) for s in sounds)
            before = r"(?:^|(?<= ))" if r.word_start else ""
            after = r"(?= |$)" if r.word_end else ""
            return re.compile(f"{before}{body}{after}"), sounds

        raise ValueError(f"Unknown mode: {r.mode}")

    # --- Phonetics -----------------------------------------------------

    def phonemize_text(self, text: str) -> str:
        """Phonemizes word by word, with a cache (espeak is only called for new words)."""
        words = words_to_phonemize(text)
        new = [w for w in dict.fromkeys(words) if w not in self._cache]
        if new:
            for word, ipa in zip(new, self.phonemizer(new)):
                self._cache[word] = normalize_phonemes(ipa).replace(" ", "")
        return " ".join(self._cache[w] for w in words)

    # --- Detection -----------------------------------------------------

    def matches(self, text: str) -> list[Rule]:
        """All rules matching the text, without cooldown or memory (each at most once)."""
        normalized = normalize_text(text)
        ipa = None
        stream = None
        found = []
        for r in self.rules:
            compiled = r._compiled
            if r.mode == "phonetic":
                if ipa is None:
                    ipa = self.phonemize_text(text)
                if r.tolerance > 0:
                    stream = stream or phoneme_stream(ipa)
                    hit = any(
                        approximate_match(
                            sounds, *stream, effective_tolerance(len(sounds), r.tolerance),
                            r.word_start, r.word_end,
                        )
                        for sounds in compiled.sounds
                    )
                else:
                    hit = any(p.search(ipa) for p in compiled.patterns)
            else:
                hit = any(p.search(normalized) for p in compiled.patterns)
            if hit:
                found.append(r)
        return found

    def analyze(self, text: str, final: bool) -> list[Rule]:
        """Call this on every Vosk result (partial or final).

        Only returns new triggers: a rule already triggered during the current
        utterance, or still in cooldown, is ignored.
        """
        now = time.monotonic()
        triggered = []
        for r in self.matches(text) if text else []:
            if r.id in self._seen_in_utterance:
                continue
            self._seen_in_utterance.add(r.id)
            if now - r._last < r.cooldown:
                continue
            r._last = now
            triggered.append(r)
        if final:
            self._seen_in_utterance.clear()
        return triggered
