"""Creates the espeak-ng phonemizer (through the phonemizer package)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

LANGUAGE = "fr-fr"


def _find_windows_dll() -> None:
    """On Windows, phonemizer does not find the DLL by itself:
    look for it in the usual install locations."""
    if sys.platform != "win32" or "PHONEMIZER_ESPEAK_LIBRARY" in os.environ:
        return
    for folder in (os.environ.get("ProgramFiles"), os.environ.get("ProgramFiles(x86)")):
        if folder:
            dll = Path(folder) / "eSpeak NG" / "libespeak-ng.dll"
            if dll.is_file():
                os.environ["PHONEMIZER_ESPEAK_LIBRARY"] = str(dll)
                return


def create_phonemizer():
    """Returns a function: list of words -> list of IPA transcriptions.

    Raises RuntimeError with a clear message if espeak-ng cannot be found.
    """
    _find_windows_dll()
    try:
        from phonemizer.backend import EspeakBackend

        # "remove-flags": without it, a foreign word comes out as "(en)laɪv(fr)", and those
        # flags would be read as sounds ("(", "e", "n", ")") by the detector.
        backend = EspeakBackend(LANGUAGE, language_switch="remove-flags")
    except Exception as e:
        raise RuntimeError(
            f"Could not initialize espeak-ng: {e}\n"
            "On Windows, install espeak-ng or set PHONEMIZER_ESPEAK_LIBRARY\n"
            "to the path of libespeak-ng.dll"
        ) from e
    return lambda words: backend.phonemize(list(words), strip=True)
