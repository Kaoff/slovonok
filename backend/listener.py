"""Microphone capture + Vosk recognition, in a dedicated thread."""

from __future__ import annotations

import json
import queue
import threading
from typing import Callable

import sounddevice as sd

import paths
from vosk import KaldiRecognizer, Model, SetLogLevel

MODELS_DIR = paths.MODELS_DIR

SetLogLevel(-1)  # silences Kaldi's verbose logs
_models: dict[str, Model] = {}  # a model takes a few seconds to load: keep it around


def load_model(name: str) -> Model:
    if name not in _models:
        path = MODELS_DIR / name
        if not path.is_dir():
            raise FileNotFoundError(f"Vosk model not found: {path}")
        _models[name] = Model(str(path))
    return _models[name]


def _windows_communications_microphone() -> str | None:
    """Name of Windows' default *communications* recording device, or None.

    PortAudio (sounddevice) only knows the regular default device,
    so we ask the Windows Core Audio API directly through pycaw.
    """
    try:
        from comtypes import CLSCTX_ALL, CoCreateInstance, CoInitialize
        from pycaw.api.mmdeviceapi import IMMDeviceEnumerator
        from pycaw.constants import CLSID_MMDeviceEnumerator, EDataFlow, ERole
        from pycaw.pycaw import AudioUtilities

        CoInitialize()  # COM must be initialized in each thread that uses it
        enumerator = CoCreateInstance(CLSID_MMDeviceEnumerator, IMMDeviceEnumerator, CLSCTX_ALL)
        endpoint = enumerator.GetDefaultAudioEndpoint(EDataFlow.eCapture.value, ERole.eCommunications.value)
        return AudioUtilities.CreateDevice(endpoint).FriendlyName
    except Exception as e:  # not on Windows, pycaw missing, no recording device…
        print(f"⚠ Could not read the default communications microphone: {e}")
        return None


def _find_input_device(name: str) -> int | None:
    """sounddevice index of an input device from its Windows name.

    MME is preferred (most tolerant). MME truncates names to 31 characters,
    hence the prefix match for long names.
    """
    apis = sd.query_hostapis()
    inputs = [
        (i, d["name"], apis[d["hostapi"]]["name"])
        for i, d in enumerate(sd.query_devices())
        if d["max_input_channels"] > 0
    ]
    for preferred_api in ("MME", "Windows WASAPI"):
        for i, device_name, api in inputs:
            if api != preferred_api:
                continue
            if device_name == name or (len(device_name) >= 31 and name.startswith(device_name)):
                return i
    return None


def resolve_microphone(microphone: str | int | None) -> str | int | None:
    """What to pass to sounddevice: the configured mic, or else the default
    communications mic, or else (None) PortAudio's default input."""
    if microphone is not None:
        return microphone
    name = _windows_communications_microphone()
    if name:
        index = _find_input_device(name)
        if index is not None:
            return index
        print(f"⚠ Default communications microphone '{name}' not found, using the default input")
    return None


def list_microphones() -> dict:
    """Microphones to choose from, one entry per physical device.

    Windows lists every device once per audio API (MME, WASAPI…). We keep the MME
    entries (the most tolerant) and use the WASAPI name as the label, since MME
    truncates names to 31 characters.
    """
    apis = sd.query_hostapis()
    devices = [
        (d["name"], apis[d["hostapi"]]["name"])
        for d in sd.query_devices()
        if d["max_input_channels"] > 0
    ]
    full_names = [name for name, api in devices if api == "Windows WASAPI"]
    preferred_api = "MME" if any(api == "MME" for _, api in devices) else None

    microphones = []
    for name, api in devices:
        if preferred_api and api != preferred_api:
            continue
        label = next((f for f in full_names if f == name or (len(name) >= 31 and f.startswith(name))), name)
        if label.startswith("Microsoft Sound Mapper"):
            continue  # MME's alias for "the default device", redundant with our default option
        microphones.append({"id": f"{name}, {api}" if preferred_api else name, "label": label})

    return {"default": _windows_communications_microphone(), "microphones": microphones}


class Listener(threading.Thread):
    """Reads the microphone and calls on_text(text, final) for every Vosk result."""

    def __init__(
        self,
        model: str,
        microphone: str | int | None,
        on_text: Callable[[str, bool], None],
        on_error: Callable[[str], None],
    ):
        super().__init__(daemon=True, name="listener")
        self.model = model
        self.microphone = microphone
        self.on_text = on_text
        self.on_error = on_error
        self._stop_event = threading.Event()
        self.device_name: str | None = None

    def stop(self) -> None:
        self._stop_event.set()

    def run(self) -> None:
        try:
            self._loop()
        except Exception as e:  # unplugged mic, missing model…
            self.on_error(str(e))

    def _loop(self) -> None:
        model = load_model(self.model)
        device = resolve_microphone(self.microphone)
        info = sd.query_devices(device, "input")
        sample_rate = int(info["default_samplerate"])
        self.device_name = info["name"]
        recognizer = KaldiRecognizer(model, sample_rate)
        audio: queue.Queue[bytes] = queue.Queue()

        def callback(indata, frames, time, status):
            audio.put(bytes(indata))

        with sd.RawInputStream(
            samplerate=sample_rate,
            blocksize=sample_rate // 4,  # 250 ms blocks
            device=device,
            dtype="int16",
            channels=1,
            callback=callback,
        ):
            last_partial = ""
            while not self._stop_event.is_set():
                try:
                    data = audio.get(timeout=0.5)
                except queue.Empty:
                    continue
                if recognizer.AcceptWaveform(data):
                    text = json.loads(recognizer.Result()).get("text", "")
                    self.on_text(text, True)
                    last_partial = ""
                else:
                    partial = json.loads(recognizer.PartialResult()).get("partial", "")
                    if partial and partial != last_partial:
                        self.on_text(partial, False)
                        last_partial = partial
