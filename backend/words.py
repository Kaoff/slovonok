"""Words added by the "add_word" punishment: choosing one in the pool and building it.

Pure functions (no engine, no threads): see test_words.py.
"""

from __future__ import annotations

import random
from typing import Callable, Iterable

from config import AddWordSettings, Word
from detection import normalize_text


def candidates(pool: Iterable[str], words: Iterable[Word]) -> list[str]:
    """Pool words that can be added: not empty, not twice in the pool, not already active.

    "Already active" ignores case and accents ("Époux" = "epoux"). A disabled word is not
    active, so it doesn't prevent adding the same text."""
    active = {normalize_text(w.word) for w in words if w.enabled}
    seen: set[str] = set()
    result = []
    for text in pool:
        text = text.strip()
        key = normalize_text(text)
        if key and key not in active and key not in seen:
            seen.add(key)
            result.append(text)
    return result


def pick_word(
    pool: Iterable[str],
    words: Iterable[Word],
    accept: Callable[[str], bool] | None = None,
    rng: random.Random | None = None,
) -> str | None:
    """A random candidate that `accept` allows (e.g. can be compiled by the detector), or None."""
    options = candidates(pool, words)
    (rng or random).shuffle(options)
    return next((text for text in options if accept is None or accept(text)), None)


def build_word(
    text: str,
    settings: AddWordSettings,
    trigger: Word | None,
    now: float,
    word_id: str,
) -> Word:
    """The new word. Its punishments are the triggering word's, or the punishment's own list."""
    if settings.punishments_from == "trigger" and trigger is not None:
        punishments = trigger.punishments.model_copy(deep=True)
    else:
        punishments = settings.punishments.model_copy(deep=True)
    return Word(
        id=word_id,
        word=text,
        mode=settings.mode,
        display_mode=settings.display_mode,
        punishments=punishments,
        auto=True,
        expires_at=now + settings.duration if settings.duration > 0 else None,
    )
