"""Local server: API, WebSocket, media files, OBS overlay and config panel.

Run: python server.py   (then add http://localhost:8765/overlay/ to OBS)
"""

from __future__ import annotations

import asyncio
import os
import shutil
import threading
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from config import MEDIA_DIR, Config, ConfigStore
from engine import Engine
from media import make_playable, media_type, needs_conversion

HOST = "127.0.0.1"
PORT = 8765
OVERLAY_DIR = Path(__file__).parent / "overlay"
PANEL_DIR = Path(__file__).parent.parent / "frontend" / "build"  # SvelteKit static build

MEDIA_DIR.mkdir(parents=True, exist_ok=True)
# SLOVONOK_NO_LISTENING=1: starts without the microphone (tests, overlay development).
engine = Engine(ConfigStore(), listening_enabled=os.environ.get("SLOVONOK_NO_LISTENING") != "1")


def convert_existing_media() -> None:
    """Converts media added before conversion existed (or copied by hand into data/media),
    and points the punishments that use them to the converted files."""
    renamed = {}
    for file in sorted(MEDIA_DIR.iterdir()):
        try:
            if file.is_file() and needs_conversion(file):
                print(f"🎞  Converting {file.name} so the screen window can play it…")
                renamed[file.name] = make_playable(file).name
        except Exception as e:  # ffmpeg missing, broken file…
            print(f"⚠ {e}")
    if renamed:
        config = engine.store.read()
        for punishment in config.punishments:
            punishment.file = renamed.get(punishment.file, punishment.file)
        engine.update_config(config)
        print(f"🎞  Converted: {', '.join(f'{a} → {b}' for a, b in renamed.items())}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    engine.broadcaster.loop = asyncio.get_running_loop()
    threading.Thread(target=convert_existing_media, daemon=True, name="media").start()
    yield
    engine.stop_listening()


app = FastAPI(title="Slovonok", lifespan=lifespan)

# The panel's dev server (Vite) runs on another port during development.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Config ----------------------------------------------------------------


@app.get("/api/config")
def get_config() -> Config:
    return engine.store.read()


@app.put("/api/config")
def put_config(config: Config) -> Config:
    """Saves the whole config. Word counters are kept (see /api/words/{id}/reset)."""
    return engine.update_config(config)


@app.post("/api/words/{word_id}/reset")
def reset_word_count(word_id: str):
    if not engine.reset_count(word_id):
        raise HTTPException(404, "Unknown word")
    return {"ok": True}


# --- Status and devices ----------------------------------------------------


@app.get("/api/status")
def status():
    return engine.status()


@app.get("/api/microphones")
def microphones():
    from listener import list_microphones

    return list_microphones()


@app.get("/api/screens")
def screens():
    return engine.screens


# --- Media -----------------------------------------------------------------


@app.get("/api/media")
def list_media():
    return [
        {"file": f.name, "type": media_type(f), "size": f.stat().st_size}
        for f in sorted(MEDIA_DIR.iterdir(), key=lambda f: f.name.lower())
        if f.is_file() and media_type(f) and ".part." not in f.name  # skip conversions in progress
    ]


@app.post("/api/media")
def upload_media(file: UploadFile):
    name = Path(file.filename or "").name  # never trust a path sent by the client
    if not name or media_type(Path(name)) is None:
        raise HTTPException(400, "Unsupported file type")
    target = MEDIA_DIR / name
    stem, suffix, n = target.stem, target.suffix, 2
    while target.exists():  # never overwrite: "jumpscare (2).mp4"
        target = MEDIA_DIR / f"{stem} ({n}){suffix}"
        n += 1
    with target.open("wb") as out:
        shutil.copyfileobj(file.file, out)
    try:
        # e.g. an H.264 MP4 becomes a VP9 WebM: the screen window can't play H.264
        target = make_playable(target)
    except Exception as e:
        target.unlink(missing_ok=True)
        raise HTTPException(422, str(e)) from e
    return {"file": target.name, "type": media_type(target), "size": target.stat().st_size}


@app.delete("/api/media/{name}")
def delete_media(name: str):
    target = MEDIA_DIR / Path(name).name
    if not target.is_file():
        raise HTTPException(404, "Unknown file")
    used_by = [p.name or p.id for p in engine.store.read().punishments if p.file == target.name]
    if used_by:
        raise HTTPException(409, f"Used by: {', '.join(used_by)}")
    target.unlink()
    return {"ok": True}


# --- Tests -----------------------------------------------------------------


@app.post("/api/punishments/{punishment_id}/test")
def test_punishment(punishment_id: str):
    result = engine.trigger_punishment(punishment_id)
    if result is None:
        raise HTTPException(404, "Unknown punishment")
    return {"ok": True, **result}


class Simulation(BaseModel):
    text: str


@app.post("/api/simulate")
def simulate(simulation: Simulation):
    return {"triggered": engine.simulate(simulation.text)}


# --- WebSocket -------------------------------------------------------------


@app.websocket("/ws")
async def websocket(ws: WebSocket):
    await ws.accept()
    engine.broadcaster.clients.add(ws)
    await ws.send_json({"type": "config", "config": engine.store.read().model_dump()})
    try:
        while True:
            await ws.receive_text()  # messages are ignored: only used to detect disconnection
    except WebSocketDisconnect:
        pass
    finally:
        engine.broadcaster.clients.discard(ws)


# --- Static files ----------------------------------------------------------

app.mount("/media", StaticFiles(directory=MEDIA_DIR), name="media")
app.mount("/overlay", StaticFiles(directory=OVERLAY_DIR, html=True), name="overlay")
if PANEL_DIR.is_dir():
    # Mounted last: "/" would otherwise catch every route above.
    app.mount("/", StaticFiles(directory=PANEL_DIR, html=True), name="panel")


if __name__ == "__main__":
    import uvicorn

    print(f"OBS overlay: http://localhost:{PORT}/overlay/")
    uvicorn.run(app, host=HOST, port=PORT, log_level="warning")
