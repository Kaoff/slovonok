"""App core: wires listening, detection, punishments and event broadcasting together."""

from __future__ import annotations

import asyncio
import random
import threading
import time
from typing import Any

from fastapi import WebSocket

from config import Config, ConfigStore, Word
from detection import Detector, Rule
from listener import Listener
from phonetics import create_phonemizer


class Broadcaster:
    """Sends events to every WebSocket client (overlays, panel).

    publish() can be called from any thread.
    """

    def __init__(self):
        self.clients: set[WebSocket] = set()
        self.loop: asyncio.AbstractEventLoop | None = None

    def publish(self, event: dict[str, Any]) -> None:
        if self.loop and not self.loop.is_closed():
            asyncio.run_coroutine_threadsafe(self._broadcast(event), self.loop)

    async def _broadcast(self, event: dict[str, Any]) -> None:
        for ws in list(self.clients):
            try:
                await ws.send_json(event)
            except Exception:
                self.clients.discard(ws)


class Engine:
    def __init__(self, store: ConfigStore, listening_enabled: bool = True):
        self.store = store
        self.broadcaster = Broadcaster()
        self.listening_enabled = listening_enabled
        self.listener: Listener | None = None
        self.screens: list[dict[str, Any]] = []  # filled by the desktop app (Qt knows the screens)
        self.listener_error: str | None = None
        self._lock = threading.Lock()

        try:
            self.phonemizer = create_phonemizer()
            self.phonetics_error = None
        except RuntimeError as e:
            print(f"⚠ {e}\n  Words in phonetic mode will be ignored.")
            self.phonemizer = None
            self.phonetics_error = str(e)

        self.detector = Detector([], self.phonemizer)
        self.apply(store.read())
        threading.Thread(target=self._watch_config_file, daemon=True, name="config").start()

    # --- Configuration -------------------------------------------------

    def apply(self, config: Config) -> None:
        """Reloads detection rules, and restarts listening if the mic or model changed."""
        rules = [
            Rule(
                id=w.id,
                word=w.word,
                mode=w.mode,
                word_end=w.word_end,
                word_start=w.word_start,
                plural=w.plural,
                cooldown=config.cooldown,
            )
            for w in config.words
            if w.enabled and w.word.strip() and (w.mode == "exact" or self.phonemizer)
        ]
        with self._lock:
            self.detector.update(rules)

        if self.listening_enabled:
            l = self.listener
            if l is None or not l.is_alive() or (l.microphone, l.model) != (config.microphone, config.model):
                self.start_listening(config)

    def update_config(self, config: Config) -> Config:
        config = self.store.replace(config)
        self.apply(config)
        self.publish_config()
        return config

    def publish_config(self) -> None:
        self.broadcaster.publish({"type": "config", "config": self.store.read().model_dump()})

    def reset_count(self, word_id: str) -> bool:
        if self.store.reset_count(word_id) is None:
            return False
        self.publish_config()
        return True

    def _watch_config_file(self) -> None:
        """Reloads data/config.json when it is edited by hand (until the panel exists)."""
        while True:
            time.sleep(1)
            try:
                config = self.store.reload_if_modified()
            except ValueError as e:
                print(f"⚠ Invalid config.json, keeping the previous config:\n{e}")
                continue
            if config:
                self.apply(config)
                self.broadcaster.publish({"type": "config", "config": config.model_dump()})
                active = ", ".join(f"'{w.word}' ({w.punishments.strategy})" for w in config.words if w.enabled)
                print(f"🔄 Config reloaded: {active or 'no active word'}")

    # --- Listening -----------------------------------------------------

    def start_listening(self, config: Config) -> None:
        self.stop_listening()
        self.listener_error = None
        self.listener = Listener(config.model, config.microphone, self.on_text, self.on_listener_error)
        self.listener.start()

    def stop_listening(self) -> None:
        if self.listener:
            self.listener.stop()
            self.listener.join(timeout=2)
            self.listener = None

    def on_listener_error(self, message: str) -> None:
        if threading.current_thread() is not self.listener:
            return
        self.listener_error = message
        print(f"⚠ Listening stopped: {message}")
        self.broadcaster.publish({"type": "error", "message": message})

    def status(self) -> dict[str, Any]:
        l = self.listener
        return {
            "listening": bool(l and l.is_alive()),
            "microphone": l.device_name if l else None,
            "listener_error": self.listener_error,
            "phonetics_error": self.phonetics_error,
        }

    # --- Detection and punishments -------------------------------------

    def on_text(self, text: str, final: bool) -> None:
        # Ignore a listener that is being replaced but hasn't stopped yet:
        # two listeners at once would publish every sentence twice.
        if threading.current_thread() is not self.listener:
            return
        self.broadcaster.publish({"type": "transcription", "text": text, "final": final})
        if final and text:
            print(f"   {text}")
        with self._lock:
            triggered = self.detector.analyze(text, final)
        for rule in triggered:
            self.punish(rule.id)

    def punish(self, word_id: str) -> None:
        word = self.store.increment(word_id)
        if word is None:
            return
        config = self.store.read()
        print(f"🚨 '{word.word}' (×{word.count})")
        self.broadcaster.publish({"type": "detection", "word": word.model_dump()})
        for punishment_id in self.select_punishments(word):
            self.trigger_punishment(punishment_id, config, word)

    @staticmethod
    def select_punishments(word: Word) -> list[str]:
        ids = word.punishments.ids
        if not ids:
            return []
        if word.punishments.strategy == "random":
            return [random.choice(ids)]
        if word.punishments.strategy == "escalation":
            # 1st time → 1st punishment, etc.; once at the end of the list, stay on the last one.
            return [ids[min(word.count, len(ids)) - 1]]
        return list(ids)

    def trigger_punishment(self, punishment_id: str, config: Config | None = None, word: Word | None = None) -> bool:
        config = config or self.store.read()
        punishment = next((p for p in config.punishments if p.id == punishment_id), None)
        if punishment is None:
            return False
        self.broadcaster.publish({
            "type": "punishment",
            "punishment": punishment.model_dump(),
            "word": word.word if word else None,
        })
        return True

    def simulate(self, text: str) -> list[str]:
        """Acts as if the microphone heard this text (handy for testing without speaking)."""
        with self._lock:
            triggered = self.detector.analyze(text, final=True)
        for rule in triggered:
            self.punish(rule.id)
        return [r.word for r in triggered]
