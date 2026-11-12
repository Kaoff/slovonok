# PyInstaller spec for the Windows app (one folder, no console).
# Build with packaging/build.ps1, which checks the result with `Slovonok.exe --smoke`.
#
# What goes in the package, besides the Python code and the libraries PyInstaller finds itself:
#   overlay/  the OBS overlays            panel/    the config panel (frontend build)
#   models/   the Vosk model              espeak/   libespeak-ng.dll + espeak-ng-data (GPL-3.0)
#   assets/   the icon                    vosk's DLLs, PortAudio, ffmpeg (imageio-ffmpeg)

import os
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs, collect_submodules

ROOT = Path(SPECPATH).parent  # noqa: F821 - SPECPATH is provided by PyInstaller
BACKEND = ROOT / "backend"
ESPEAK = Path(os.environ.get("ESPEAK_NG_DIR", r"C:\Program Files\eSpeak NG"))
MODEL = os.environ.get("SLOVONOK_MODEL", "vosk-model-small-fr-0.22")


def need(path: Path) -> str:
    if not path.exists():
        raise SystemExit(f"Missing for the package: {path}")
    return str(path)


datas = [
    (need(BACKEND / "overlay"), "overlay"),
    (need(ROOT / "frontend" / "build"), "panel"),  # npm run build first
    (need(BACKEND / "models" / MODEL), f"models/{MODEL}"),
    (need(BACKEND / "assets"), "assets"),
    (need(ESPEAK / "espeak-ng-data"), "espeak/espeak-ng-data"),
    (need(ROOT / "LICENSE"), "licenses"),
    (need(ROOT / "THIRD_PARTY_NOTICES.md"), "licenses"),
]
binaries = [(need(ESPEAK / "libespeak-ng.dll"), "espeak")]

# Libraries that load files by path at run time, which the import analysis can't see
binaries += collect_dynamic_libs("vosk")  # libvosk.dll and the MinGW runtime it needs
datas += collect_data_files("imageio_ffmpeg")  # the ffmpeg executable
datas += collect_data_files("phonemizer")
datas += [
    (src, dest)
    for src, dest in collect_data_files("_sounddevice_data")  # PortAudio: keep the 64-bit Windows build
    if "64bit" in os.path.basename(src) and "arm64" not in src
]

hiddenimports = (
    collect_submodules("uvicorn")  # loaded by name: the event loop, protocols, lifespan...
    + collect_submodules("websockets")
    + ["httptools", "multipart", "comtypes", "comtypes.client", "pycaw", "pycaw.pycaw"]
)

# Not used by the app, and big
excludes = ["tkinter", "matplotlib", "IPython", "pytest", "PySide6.QtQuick3D", "PySide6.QtDesigner"]

a = Analysis(
    [str(BACKEND / "main.py")],
    pathex=[str(BACKEND)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=excludes,
    noarchive=False,
)
pyz = PYZ(a.pure)  # noqa: F821

exe = EXE(  # noqa: F821
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,  # one folder: the libraries stay beside the exe
    name="Slovonok",
    console=False,  # a windowed app; its output goes to %APPDATA%\Slovonok\logs
    icon=str(BACKEND / "assets" / "icon.ico"),
    upx=False,  # UPX corrupts Qt's DLLs
)
coll = COLLECT(  # noqa: F821
    exe,
    a.binaries,
    a.datas,
    upx=False,
    name="Slovonok",
)
