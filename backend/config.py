"""App configuration: data models + reading/writing the JSON file."""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

DATA_DIR = Path(__file__).parent / "data"
MEDIA_DIR = DATA_DIR / "media"
CONFIG_FILE = DATA_DIR / "config.json"


class ChromaKey(BaseModel):
    enabled: bool = False
    color: str = "#00ff00"
    similarity: float = 0.4  # same scale as the OBS filter (400/1000)
    smoothness: float = 0.08
    spill: float = 0.1  # reduces the green fringe on edges


class Punishment(BaseModel):
    id: str
    name: str = ""
    type: Literal["sound", "image", "video"]
    file: str  # file name in data/media
    volume: float = 1.0
    duration: float = 3.0  # images only, in seconds
    chroma_key: ChromaKey = Field(default_factory=ChromaKey)


class PunishmentSelection(BaseModel):
    strategy: Literal["all", "random", "escalation"] = "all"
    ids: list[str] = Field(default_factory=list)


class Word(BaseModel):
    id: str
    word: str
    mode: Literal["phonetic", "exact"] = "phonetic"
    word_end: bool = True
    word_start: bool = False
    plural: bool = True
    enabled: bool = True
    count: int = 0
    punishments: PunishmentSelection = Field(default_factory=PunishmentSelection)


class ScreenDisplay(BaseModel):
    """Punishments shown on the streamer's own screen, above the game."""

    enabled: bool = True
    monitor: int = 0  # index in the list of screens (0 = first one)
    sound: bool = True  # the streamer hears the punishments
    hide_from_capture: bool = True  # invisible to OBS display capture (the stream uses the overlay)


class OverlayDisplay(BaseModel):
    """Punishments shown in the OBS browser source."""

    sound: bool = False  # off by default: OBS usually captures the screen window's sound already


class Display(BaseModel):
    screen: ScreenDisplay = Field(default_factory=ScreenDisplay)
    overlay: OverlayDisplay = Field(default_factory=OverlayDisplay)


class Config(BaseModel):
    language: Literal["en", "fr"] = "fr"  # config panel language
    microphone: str | int | None = None  # "Name, API" or index; None = Windows default communications mic
    model: str = "vosk-model-small-fr-0.22"  # folder in models/
    cooldown: float = 5.0
    display: Display = Field(default_factory=Display)
    words: list[Word] = Field(default_factory=list)
    punishments: list[Punishment] = Field(default_factory=list)


DEFAULT_CONFIG = Config(
    words=[
        Word(
            id="w-epoux",
            word="époux",
            punishments=PunishmentSelection(strategy="all", ids=["p-mistake", "p-jumpscare"]),
        )
    ],
    punishments=[
        Punishment(id="p-mistake", name="Mistake", type="sound", file="mistake.mp3"),
        Punishment(
            id="p-jumpscare",
            name="Jumpscare",
            type="video",
            file="jumpscare.mp4",
            chroma_key=ChromaKey(enabled=True),
        ),
    ],
)


class ConfigStore:
    """Thread-safe access to the config (listening runs in another thread than the server)."""

    def __init__(self, file: Path = CONFIG_FILE):
        self.file = file
        self._lock = threading.RLock()
        self._mtime = 0.0
        if file.is_file():
            self._config = Config.model_validate_json(file.read_text(encoding="utf-8"))
            self._mtime = file.stat().st_mtime
        else:
            self._config = DEFAULT_CONFIG.model_copy(deep=True)
            self.save()

    def read(self) -> Config:
        with self._lock:
            return self._config.model_copy(deep=True)

    def replace(self, config: Config, keep_counts: bool = True) -> Config:
        """Replaces the config. By default, word counters keep their stored value:
        they change between the moment the panel reads the config and saves it."""
        with self._lock:
            if keep_counts:
                counts = {w.id: w.count for w in self._config.words}
                for word in config.words:
                    word.count = counts.get(word.id, 0)
            self._config = config
            self.save()
            return config.model_copy(deep=True)

    def reset_count(self, word_id: str) -> Word | None:
        with self._lock:
            for word in self._config.words:
                if word.id == word_id:
                    word.count = 0
                    self.save()
                    return word.model_copy(deep=True)
        return None

    def increment(self, word_id: str) -> Word | None:
        """Increments a word's counter and returns an updated copy of the word."""
        with self._lock:
            for word in self._config.words:
                if word.id == word_id:
                    word.count += 1
                    self.save()
                    return word.model_copy(deep=True)
        return None

    def reload_if_modified(self) -> Config | None:
        """Re-reads the file if it was edited by hand. Returns the new config, or None.

        Raises ValueError if the JSON is invalid (the previous config is kept)."""
        with self._lock:
            try:
                mtime = self.file.stat().st_mtime
            except FileNotFoundError:
                return None
            if mtime == self._mtime:
                return None
            self._mtime = mtime
            try:
                config = Config.model_validate_json(self.file.read_text(encoding="utf-8"))
            except Exception as e:
                raise ValueError(str(e)) from e
            self._config = config
            return config.model_copy(deep=True)

    def save(self) -> None:
        with self._lock:
            self.file.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.file.with_suffix(".tmp")
            tmp.write_text(
                json.dumps(self._config.model_dump(), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            tmp.replace(self.file)  # atomic write: never a half-written file
            self._mtime = self.file.stat().st_mtime  # our own writes don't trigger a reload
