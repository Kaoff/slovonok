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


class PunishmentSelection(BaseModel):
    strategy: Literal["all", "random", "escalation"] = "all"
    ids: list[str] = Field(default_factory=list)


class AddWordSettings(BaseModel):
    """Options of the "add_word" punishment: adds a forbidden word to the list."""

    pool: list[str] = Field(default_factory=list)  # candidates, one is picked at random
    mode: Literal["phonetic", "exact"] = "phonetic"
    display_mode: Literal["shown", "hidden", "partial"] = "shown"
    # Punishments of the new word: copy the triggering word's, or use `punishments` below
    # (also used when there is no triggering word, e.g. when testing the punishment).
    punishments_from: Literal["trigger", "list"] = "trigger"
    punishments: PunishmentSelection = Field(default_factory=PunishmentSelection)
    duration: float = 0.0  # seconds before the word is removed; 0 = until removed by hand


class Punishment(BaseModel):
    id: str
    name: str = ""
    type: Literal["sound", "image", "video", "add_word"]
    file: str = ""  # file name in data/media (not used by add_word)
    volume: float = 1.0
    duration: float = 3.0  # images only, in seconds
    chroma_key: ChromaKey = Field(default_factory=ChromaKey)
    add_word: AddWordSettings = Field(default_factory=AddWordSettings)


class Word(BaseModel):
    id: str
    word: str
    mode: Literal["phonetic", "exact"] = "phonetic"
    word_end: bool = True
    word_start: bool = False
    plural: bool = True
    enabled: bool = True
    count: int = 0
    display_mode: Literal["shown", "hidden", "partial"] = "shown"  # in the words overlay
    # "Sounds like": what Vosk transcribes when the word is said (it can't output invented
    # words, so it outputs the closest French). Each one triggers the word, same options.
    variants: list[str] = Field(default_factory=list)
    # Phonetic mode: how many sounds may differ (see fuzzy.py). More = more false positives.
    tolerance: int = Field(default=0, ge=0, le=2)
    punishments: PunishmentSelection = Field(default_factory=PunishmentSelection)
    # Words added by an "add_word" punishment: the server decides when they exist (see ConfigStore.replace)
    auto: bool = False
    expires_at: float | None = None  # Unix time at which the word is removed


class ScreenDisplay(BaseModel):
    """Punishments shown on the streamer's own screen, above the game."""

    enabled: bool = True
    monitor: int = 0  # index in the list of screens (0 = first one)
    sound: bool = True  # the streamer hears the punishments
    hide_from_capture: bool = True  # invisible to OBS display capture (the stream uses the overlay)


class OverlayDisplay(BaseModel):
    """Punishments shown in the OBS browser source."""

    sound: bool = False  # off by default: OBS usually captures the screen window's sound already


class WordsDisplay(BaseModel):
    """List of forbidden words in the second OBS browser source (/overlay/words/)."""

    font_size: float = 1.75  # rem
    color: str = "#00f0ff"
    align: Literal["left", "center", "right"] = "left"
    position: Literal["top", "middle", "bottom"] = "top"
    show_count: bool = True
    # Animations (overlay/words/animations.css)
    enter_animation: Literal["none", "fade", "slide", "pop", "glitch"] = "slide"
    exit_animation: Literal["none", "fade", "slide", "shrink", "glitch"] = "fade"
    hit_animation: Literal["none", "shake", "pulse", "flash", "glitch"] = "shake"
    # When enabled, the built-in look (overlay/words/default.css) is not loaded at all:
    # custom_css is the only style, animations aside.
    custom_css_enabled: bool = False
    custom_css: str = ""


class Display(BaseModel):
    screen: ScreenDisplay = Field(default_factory=ScreenDisplay)
    overlay: OverlayDisplay = Field(default_factory=OverlayDisplay)
    words: WordsDisplay = Field(default_factory=WordsDisplay)


class Config(BaseModel):
    language: Literal["en", "fr"] = "fr"  # config panel language
    microphone: str | int | None = None  # "Name, API" or index; None = Windows default communications mic
    model: str = "vosk-model-small-fr-0.22"  # folder in models/
    cooldown: float = 5.0
    max_active_words: int = 10  # "add_word" punishments stop here; 0 = no limit
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
        """Replaces the config, except what the server owns:
        - word counters keep their stored value (they change between the moment the panel
          reads the config and saves it) ;
        - words added by a punishment are not resurrected once the server removed them
          (expired), and keep their expiry: a panel with an outdated word list can't undo that.
        """
        with self._lock:
            current = {w.id: w for w in self._config.words}
            words = []
            for word in config.words:
                old = current.get(word.id)
                if old is None and word.auto:
                    continue
                if old:
                    word.auto, word.expires_at = old.auto, old.expires_at
                if keep_counts:
                    word.count = old.count if old else 0
                words.append(word)
            config.words = words
            self._config = config
            self.save()
            return config.model_copy(deep=True)

    def add_word(self, word: Word) -> None:
        with self._lock:
            self._config.words.append(word)
            self.save()

    def expire_words(self, now: float) -> list[Word]:
        """Removes the words whose lifetime is over and returns them."""
        with self._lock:
            expired = [w for w in self._config.words if w.expires_at is not None and w.expires_at <= now]
            if expired:
                self._config.words = [w for w in self._config.words if w not in expired]
                self.save()
            return [w.model_copy(deep=True) for w in expired]

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
