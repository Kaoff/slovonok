"""Standalone prototype: prints the live Vosk transcript and detects forbidden words.

Usage:
    python listen.py --list-devices                 # list audio devices
    python listen.py                                # default communications mic, transcript only
    python listen.py --phonetic
    python listen.py --word époux --word "en vrai"
    python listen.py --word époux --exact           # exact word mode
    python listen.py --device "My Mic, MME"         # specific mic (name from --list-devices)
"""

import argparse
import json
import queue
import sys
from pathlib import Path

import sounddevice as sd
from vosk import KaldiRecognizer, Model, SetLogLevel

from detection import Detector, Rule
from listener import resolve_microphone
from phonetics import create_phonemizer

DEFAULT_MODEL = Path(__file__).parent / "models" / "vosk-model-small-fr-0.22"


def main():
    parser = argparse.ArgumentParser(description="Live Vosk transcript + forbidden words")
    parser.add_argument("--list-devices", action="store_true", help="list audio devices")
    parser.add_argument(
        "--device",
        type=lambda v: int(v) if v.isdigit() else v,
        default=None,
        help='microphone index or "Name, API" (see --list-devices); default: Windows default communications mic',
    )
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL, help="Vosk model folder")
    parser.add_argument("--phonetic", action="store_true", help="print the phonetic transcript")
    parser.add_argument("--word", action="append", default=[], help="forbidden word (repeatable)")
    parser.add_argument("--exact", action="store_true", help="exact word mode instead of phonetic")
    parser.add_argument("--anywhere", action="store_true", help="phonetic: don't require a word end")
    args = parser.parse_args()

    if args.list_devices:
        print(sd.query_devices())
        return

    if not args.model.is_dir():
        sys.exit(
            f"Model not found: {args.model}\n"
            "Download vosk-model-small-fr-0.22 from https://alphacephei.com/vosk/models\n"
            "and unzip it into backend/models/"
        )

    mode = "exact" if args.exact else "phonetic"
    needs_phonetics = args.phonetic or (args.word and mode == "phonetic")
    try:
        phonemizer = create_phonemizer() if needs_phonetics else None
    except RuntimeError as e:
        sys.exit(str(e))

    rules = [
        Rule(id=f"w{i}", word=word, mode=mode, word_end=not args.anywhere)
        for i, word in enumerate(args.word)
    ]
    detector = Detector(rules, phonemizer)

    # Use the mic's native sample rate: Vosk adapts to it,
    # and it avoids errors from devices that refuse 16 kHz.
    device = resolve_microphone(args.device)
    info = sd.query_devices(device, "input")
    sample_rate = int(info["default_samplerate"])

    SetLogLevel(-1)  # silences Kaldi's verbose logs
    model = Model(str(args.model))
    recognizer = KaldiRecognizer(model, sample_rate)

    audio = queue.Queue()

    def callback(indata, frames, time, status):
        if status:
            print(status, file=sys.stderr)
        audio.put(bytes(indata))

    def report(triggered):
        for r in triggered:
            print(f"\r\033[K🚨 FORBIDDEN WORD: '{r.word}'")

    with sd.RawInputStream(
        samplerate=sample_rate,
        blocksize=sample_rate // 4,  # 250 ms blocks
        device=device,
        dtype="int16",
        channels=1,
        callback=callback,
    ):
        print(f"🎙  Listening on '{info['name']}' ({sample_rate} Hz) — Ctrl+C to stop")
        for r in rules:
            print(f"   Forbidden word: '{r.word}' ({r.mode}, pattern {r._compiled.patterns[0].pattern})")
        print()

        last_partial = ""
        while True:
            data = audio.get()
            if recognizer.AcceptWaveform(data):
                text = json.loads(recognizer.Result()).get("text", "")
                if text:
                    print(f"\r\033[K✔ {text}")
                    if args.phonetic:
                        print(f"  /{detector.phonemize_text(text)}/")
                report(detector.analyze(text, final=True))
                last_partial = ""
            else:
                partial = json.loads(recognizer.PartialResult()).get("partial", "")
                if partial and partial != last_partial:
                    # Detect on partial results to react mid-sentence.
                    report(detector.analyze(partial, final=False))
                    print(f"\r\033[K… {partial}", end="", flush=True)
                    last_partial = partial


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nStopped.")
