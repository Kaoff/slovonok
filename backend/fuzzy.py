"""Approximate matching of a word's sounds inside a transcript's sounds.

Pure functions on lists of sound segments (no espeak, no Vosk): see test_fuzzy.py.

Why: Vosk only outputs words of its vocabulary, so an invented word ("Pakwaf") comes out as
whatever French is closest ("pas quoi", "par quoi", "pas voir"). Allowing a few sound edits
catches those variants without having heard them first.
"""

from __future__ import annotations

# At least this many sounds of the target must really match: with fewer, a few edits would
# turn almost anything into a match.
MIN_MATCHED_SOUNDS = 4


def effective_tolerance(target_length: int, tolerance: int) -> int:
    """The edits actually allowed for a target of this many sounds (short words get fewer)."""
    return max(0, min(tolerance, target_length - MIN_MATCHED_SOUNDS))


def approximate_match(
    target: list[str],
    text: list[str],
    starts: list[bool],
    max_edits: int,
    word_start: bool = False,
    word_end: bool = True,
) -> bool:
    """True if `target` appears in `text` with at most `max_edits` edits (a sound replaced,
    added or missing). Spaces between words cost nothing, as with the exact regex.

    `starts[j]` says that text[j] is the first sound of a word. With `word_start`, the match
    must begin on such a sound; with `word_end`, it must end right before one (or at the end).

    Sellers' algorithm: edit distance where the match may start anywhere in the text.
    """
    m, n = len(target), len(text)
    if m == 0:
        return False
    infinity = m + n + 1

    def may_start(j: int) -> bool:
        return not word_start or j == 0 or (j < n and starts[j])

    # column[i] = fewest edits to align target[:i] with some stretch of text ending here
    column = list(range(m + 1))
    for j in range(1, n + 1):
        previous = column
        column = [0 if may_start(j) else infinity] + [0] * m
        for i in range(1, m + 1):
            substitution = previous[i - 1] + (0 if target[i - 1] == text[j - 1] else 1)
            column[i] = min(substitution, previous[i] + 1, column[i - 1] + 1)
        if column[m] <= max_edits and (not word_end or j == n or starts[j]):
            return True
    return False
