"""Where things live, in development and in the packaged app (PyInstaller).

- RESOURCE_DIR: read-only files shipped with the app (overlay, panel, models, espeak).
- DATA_DIR: what the user changes (config, media, logs). Never inside the install folder: the
  updater replaces that folder, and Program Files-like locations aren't writable.

Development keeps the repo layout (data in backend/data), so nothing changes there.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

FROZEN = bool(getattr(sys, "frozen", False))
BACKEND_DIR = Path(__file__).resolve().parent

# PyInstaller (onedir) unpacks the app's files in `_internal`, whose path it gives as _MEIPASS
if FROZEN:
    RESOURCE_DIR = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
else:
    RESOURCE_DIR = BACKEND_DIR

OVERLAY_DIR = RESOURCE_DIR / "overlay"
MODELS_DIR = RESOURCE_DIR / "models"
# The panel's static build: in the repo it's frontend/build, in the package it is copied to "panel"
PANEL_DIR = RESOURCE_DIR / "panel" if FROZEN else BACKEND_DIR.parent / "frontend" / "build"
ESPEAK_DIR = RESOURCE_DIR / "espeak"  # libespeak-ng.dll and espeak-ng-data, packaged only
ICON_FILE = RESOURCE_DIR / "assets" / "icon.ico"


def _data_dir() -> Path:
    override = os.environ.get("SLOVONOK_DATA_DIR")
    if override:
        return Path(override)
    if FROZEN:
        return Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming") / "Slovonok"
    return BACKEND_DIR / "data"


DATA_DIR = _data_dir()
LOG_FILE = DATA_DIR / "logs" / "slovonok.log"
LOG_MAX_BYTES = 2_000_000


def configure_runtime() -> None:
    """Call first thing in the packaged app, before phonemizer or any logging library is imported."""
    if not FROZEN:
        return
    _use_bundled_espeak()
    _redirect_output_to_log()


def _use_bundled_espeak() -> None:
    library = ESPEAK_DIR / "libespeak-ng.dll"
    if library.is_file():
        os.environ["PHONEMIZER_ESPEAK_LIBRARY"] = str(library)
        os.environ["ESPEAK_DATA_PATH"] = str(ESPEAK_DIR)  # the folder that contains espeak-ng-data


def _redirect_output_to_log() -> None:
    """A windowed app has no console: sys.stdout is None, which breaks logging handlers, and the
    default encoding can't print the emoji of the app's messages. Everything goes to a UTF-8 file."""
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    if LOG_FILE.exists() and LOG_FILE.stat().st_size > LOG_MAX_BYTES:
        LOG_FILE.replace(LOG_FILE.with_suffix(".log.1"))
    log = open(LOG_FILE, "a", encoding="utf-8", buffering=1)
    sys.stdout = sys.stderr = log
