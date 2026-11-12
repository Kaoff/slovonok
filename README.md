# forbidden-word

Detects a forbidden word spoken on stream and triggers punishments on the streamer's
screen and in OBS. Speech recognition is in French; the code is in English.

- `backend/`: Python desktop app (microphone, Vosk, phonetics, local server, Qt screen window)
- `backend/overlay/`: OBS overlay (browser source)
- `backend/data/`: config (`config.json`) and media files (`media/`), not versioned
- `frontend/`: config panel (SvelteKit, static build served by the backend)

## Setup (Windows)

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
