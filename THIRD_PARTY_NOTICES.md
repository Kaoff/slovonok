# Third-party notices

Slovonok is released under the **GNU General Public License v3.0** (see `LICENSE`).
It bundles or depends on the components below, each under its own license.

The GPL components matter most: the app ships `phonemizer` (GPL-3.0 or later), the espeak-ng
library (GPL-3.0 or later) and an FFmpeg build (GPL-3.0), so the app as a whole is distributed
under the GPL-3.0, and its complete source code is available at
https://github.com/Kaoff/slovonok

| Component | License | Source |
|---|---|---|
| espeak-ng (`libespeak-ng.dll`, `espeak-ng-data`) | GPL-3.0-or-later | https://github.com/espeak-ng/espeak-ng |
| phonemizer | GPL-3.0-or-later | https://github.com/bootphon/phonemizer |
| FFmpeg (executable from `imageio-ffmpeg`, a GPL build by gyan.dev) | GPL-3.0 | https://ffmpeg.org/ and https://www.gyan.dev/ffmpeg/builds/ |
| imageio-ffmpeg | BSD-2-Clause | https://github.com/imageio/imageio-ffmpeg |
| Qt for Python (PySide6), Qt, Qt WebEngine (Chromium) | LGPL-3.0 (Qt libraries are dynamically linked and can be replaced in the install folder) | https://doc.qt.io/qtforpython-6/ |
| Vosk (`libvosk.dll`) | Apache-2.0 | https://github.com/alphacep/vosk-api |
| Vosk model `vosk-model-small-fr-0.22` | Apache-2.0 (as listed on https://alphacephei.com/vosk/models) | https://alphacephei.com/vosk/models |
| PortAudio, python-sounddevice | MIT | https://github.com/spatialaudio/python-sounddevice |
| FastAPI, Starlette, Pydantic | MIT / BSD-3-Clause / MIT | https://fastapi.tiangolo.com/ |
| Uvicorn, websockets, httptools | BSD-3-Clause / BSD-3-Clause / MIT | https://www.uvicorn.org/ |
| python-multipart | Apache-2.0 | https://github.com/Kludex/python-multipart |
| pycaw, comtypes | MIT | https://github.com/AndreMiras/pycaw |
| Svelte, SvelteKit, Tailwind CSS | MIT | https://svelte.dev/ , https://tailwindcss.com/ |
| Orbitron, Share Tech Mono (fonts, via Fontsource) | SIL Open Font License 1.1 | https://fontsource.org/ |
| PyInstaller (builds the package; its bootloader is part of it) | GPL-2.0-or-later with a special exception allowing use in any program | https://pyinstaller.org/ |

Versions are those pinned by the build (`backend/requirements.txt`, `frontend/package-lock.json`).
Each package's own license text is in its distribution metadata; this list was checked against
the installed packages' metadata when it was written.
