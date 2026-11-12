# Slovonok

Slovonok (*slovo*, "word", + *zvonok*, "bell": the word that rings the bell) detects a
forbidden word spoken on stream and triggers punishments on the streamer's
screen and in OBS. Speech recognition is in French; the code is in English.

- `backend/`: Python desktop app (microphone, Vosk, phonetics, local server, Qt screen window)
- `backend/overlay/`: OBS overlay (browser source)
- `backend/data/`: config (`config.json`) and media files (`media/`), not versioned
- `frontend/`: config panel (SvelteKit, static build served by the backend)

## Install (users)

Download `Slovonok-Setup-<version>.exe` from the
[latest release](https://github.com/Kaoff/slovonok/releases/latest) and run it. It installs for
the current user (no administrator rights). The exe is not code-signed yet, so Windows SmartScreen
shows a warning on the first run: *More info → Run anyway*.

- The app lives in the **system tray**: closing its window keeps it listening; right-click the
  icon to open the panel, pause listening or quit.
- Your words, punishments, media and logs are in `%APPDATA%\Slovonok`.
- **Updates**: the app looks for a newer release at startup and every few hours, and from
  *Settings → Check for updates*. It tells you, and installs when you click *Install and restart*.

## Setup for development (Windows)

### Backend

Requires Python 3.12 (3.15 lacks prebuilt wheels for some dependencies).

```powershell
cd backend
py -3.12 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

- Vosk model: download `vosk-model-small-fr-0.22` from https://alphacephei.com/vosk/models
  and unzip it into `backend/models/`.
- espeak-ng (phonetics): install the `.msi` from the espeak-ng GitHub releases.
  It is found automatically in `C:\Program Files\eSpeak NG\`; otherwise set
  `PHONEMIZER_ESPEAK_LIBRARY` to the path of `libespeak-ng.dll`.

### Frontend

```powershell
cd frontend
npm install
```

## Run

```powershell
cd backend
python main.py
```

- **Config panel**: `npm run dev` in `frontend/`, then http://localhost:5173
  (Vite forwards `/api`, `/ws`, `/media` and `/overlay` to the backend).
  After `npm run build`, the backend serves it on http://localhost:8765/.
- **OBS**: add a browser source pointing to `http://localhost:8765/overlay/`,
  sized to the OBS canvas (e.g. 1920×1080).
- **Streamer's screen**: a transparent, click-through, always-on-top window.
  Games must run in borderless windowed mode: exclusive fullscreen hides other windows.

Sound plays on the screen window by default, since OBS usually captures desktop audio.
If the stream doesn't get the sound, enable "Play sound in the overlay" in the panel and
tick "Control audio via OBS" on the browser source.

By default the app listens to Windows' default **communications** recording device
(Sound settings → Recording); another microphone can be picked in the panel.

`python server.py` runs the server alone, without the screen window.

`python main.py --background` starts hidden in the tray. `python main.py --smoke report.json` runs
the self-test that `packaging/build.ps1` uses to check a packaged build.

## Tests

```powershell
cd backend
python -m unittest test_detection test_words test_fuzzy test_engine test_updater
cd ..\frontend
npm run check; npm run lint; npm run test:unit -- --run --project server
```

(Run vitest and the frontend build from `D:\...` with an uppercase drive letter: from `d:\...` vitest loads twice and Vite writes absolute font URLs into the CSS.)

## Building and releasing

`powershell -File packaging\build.ps1` builds the installer (PyInstaller + Inno Setup) and checks
the package with a self-test first. See [packaging/RELEASING.md](packaging/RELEASING.md) for the
whole procedure, including how an update reaches the installed apps.

## License

Slovonok is free software under the **GNU General Public License v3.0** (see `LICENSE`), because
it ships GPL components (espeak-ng, phonemizer, FFmpeg). Third-party components and their licenses
are listed in `THIRD_PARTY_NOTICES.md`.

### Testing without speaking

Use "Type a sentence to test" in the panel, or:

```powershell
Invoke-RestMethod -Method Post http://localhost:8765/api/punishments/p-jumpscare/test
Invoke-RestMethod -Method Post http://localhost:8765/api/simulate -ContentType application/json -Body '{"text":"bah des poux"}'
```

### Tests and prototype

```powershell
cd backend
python -m unittest test_detection
python listen.py --list-devices
python listen.py --word époux --phonetic
```

```powershell
cd frontend
npm run check
npm run lint
```
