"""Self-test of the app, mostly for the packaged build: `Slovonok.exe --smoke result.json`.

A bundle can start and still miss one DLL or data folder that only a rarely used feature needs
(the phonemizer, the Vosk model, ffmpeg, the Windows audio API, the web engine...). This runs each
of them once and writes a JSON report; the exit code is 0 only if everything worked. build.ps1 runs
it on the freshly built package, and refuses to make an installer if it fails.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path
from typing import Callable

import paths


def _get(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=15) as response:
        return response.read()


def run_checks(base: str, engine) -> list[dict]:
    """Every check except the web engine's (which needs the Qt event loop, see main.py)."""
    results: list[dict] = []

    def check(name: str, test: Callable[[], str]) -> None:
        try:
            results.append({"name": name, "ok": True, "detail": test()})
        except Exception as e:  # noqa: BLE001 - the report must say what failed, whatever it is
            results.append({"name": name, "ok": False, "detail": f"{type(e).__name__}: {e}"})

    def runtime() -> str:
        return f"frozen={paths.FROZEN} resources={paths.RESOURCE_DIR} data={paths.DATA_DIR}"

    def data_dir() -> str:
        with tempfile.NamedTemporaryFile(dir=paths.DATA_DIR, prefix="smoke-", delete=True):
            pass
        return "writable"

    def inside_package(path: str, what: str) -> None:
        """In the packaged app, nothing may come from the machine that built it: a test run on the
        build machine would pass with the system's espeak, and fail on the user's."""
        if paths.FROZEN:
            assert Path(path).resolve().is_relative_to(paths.RESOURCE_DIR.resolve()), f"{what} is outside the package: {path}"

    def phonemizer() -> str:
        sounds = engine.phonemize(["pakwaf", "époux"])
        assert sounds[0] == "pakwaf" and sounds[1], f"unexpected sounds: {sounds}"
        library = os.environ.get("PHONEMIZER_ESPEAK_LIBRARY", "")
        if paths.FROZEN:
            assert library, "PHONEMIZER_ESPEAK_LIBRARY is not set"
        if library:
            inside_package(library, "espeak library")
        return " / ".join(sounds)

    def vosk_model() -> str:
        from listener import load_model

        name = engine.store.read().model
        load_model(name)
        inside_package(str(paths.MODELS_DIR / name), "Vosk model")
        return name

    def ffmpeg() -> str:
        import imageio_ffmpeg

        exe = imageio_ffmpeg.get_ffmpeg_exe()
        inside_package(exe, "ffmpeg")
        out = subprocess.run([exe, "-version"], capture_output=True, text=True, timeout=30, check=True)
        return out.stdout.splitlines()[0]

    def page(path: str, expect: str) -> Callable[[], str]:
        def test() -> str:
            body = _get(base + path).decode("utf-8", "replace")
            assert expect in body, f"{path}: '{expect}' not found"
            return f"{path} ({len(body)} bytes)"

        return test

    def api(path: str, key: str) -> Callable[[], str]:
        def test() -> str:
            data = json.loads(_get(base + path))
            assert key in data, f"{path}: no '{key}' in {list(data)[:6]}"
            return f"{path} ok"

        return test

    check("runtime", runtime)
    check("data dir", data_dir)
    check("phonemizer (espeak)", phonemizer)
    check("vosk model", vosk_model)
    check("ffmpeg", ffmpeg)
    check("panel", page("/", "<html"))
    check("overlay", page("/overlay/", "<html"))
    check("words overlay", page("/overlay/words/", "<html"))
    check("overlay fonts", page("/overlay/fonts/fonts.css", "@font-face"))
    check("api status", api("/api/status", "listening"))
    check("api microphones (Windows audio)", api("/api/microphones", "microphones"))
    check("api update", api("/api/update", "current"))
    return results


def write_report(path: str, results: list[dict]) -> int:
    ok = all(r["ok"] for r in results)
    Path(path).write_text(json.dumps({"ok": ok, "checks": results}, indent=2, ensure_ascii=False), encoding="utf-8")
    for r in results:
        print(f"{'OK  ' if r['ok'] else 'FAIL'} {r['name']}: {r['detail']}", file=sys.__stdout__ or sys.stdout)
    return 0 if ok else 1
