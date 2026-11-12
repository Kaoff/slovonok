"""Makes media files playable everywhere punishments are shown.

The screen window uses Qt WebEngine, which is built without patented codecs:
it cannot play H.264 video or AAC audio (the usual MP4 from a phone or a
download), while OBS and Chrome can. Such files are converted once, when they
enter the media library, to free codecs every target plays:
- videos → WebM (VP9 + Opus)
- sounds → Ogg (Opus)

ffmpeg comes from the imageio-ffmpeg package (a static build, nothing to install).
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

VIDEO_SUFFIXES = {".mp4", ".webm", ".mov", ".mkv"}
SOUND_SUFFIXES = {".mp3", ".wav", ".ogg", ".opus", ".m4a", ".flac", ".aac"}
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".avif", ".svg"}

# Codecs Qt WebEngine (and every browser) can decode without patented codecs
PLAYABLE_VIDEO = {"vp8", "vp9", "av1", "theora"}
PLAYABLE_AUDIO = {"opus", "vorbis", "mp3", "flac"} | {f"pcm_{f}" for f in ("s16le", "s24le", "f32le", "u8")}


def media_type(file: Path) -> str | None:
    suffix = file.suffix.lower()
    if suffix in VIDEO_SUFFIXES:
        return "video"
    if suffix in SOUND_SUFFIXES:
        return "sound"
    if suffix in IMAGE_SUFFIXES:
        return "image"
    return None


def _ffmpeg() -> str:
    import imageio_ffmpeg

    return imageio_ffmpeg.get_ffmpeg_exe()


def probe(file: Path) -> tuple[str | None, str | None]:
    """(video codec, audio codec) of a file, None when it has no such stream."""
    result = subprocess.run(
        [_ffmpeg(), "-hide_banner", "-i", str(file)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    # "Stream #0:0[0x1](und): Video: h264 (Main) ..." — cover art counts as a video stream,
    # so attached pictures are ignored.
    video = next(
        (
            m.group(1)
            for m in re.finditer(r"Stream #\S+.*?: Video: (\w+).*", result.stderr)
            if "attached pic" not in m.group(0)
        ),
        None,
    )
    audio = re.search(r"Stream #\S+.*?: Audio: (\w+)", result.stderr)
    return video, audio.group(1) if audio else None


def needs_conversion(file: Path) -> bool:
    """Raises ValueError if the file has no stream of its kind (not a real video or sound)."""
    kind = media_type(file)
    if kind == "image" or kind is None:
        return False
    video, audio = probe(file)
    if (kind == "video" and video is None) or (kind == "sound" and audio is None):
        raise ValueError(f"{file.name} is not a readable {kind} file")
    if kind == "video":
        return (video is not None and video not in PLAYABLE_VIDEO) or (
            audio is not None and audio not in PLAYABLE_AUDIO
        )
    return audio is not None and audio not in PLAYABLE_AUDIO


def _unique(path: Path) -> Path:
    stem, suffix, n = path.stem, path.suffix, 2
    while path.exists():
        path = path.with_name(f"{stem} ({n}){suffix}")
        n += 1
    return path


def convert(file: Path) -> Path:
    """Converts to free codecs next to the original, deletes the original, returns the new file."""
    kind = media_type(file)
    if kind == "video":
        target = _unique(file.with_suffix(".webm"))
        codecs = [
            # Constant quality VP9; "good" + cpu-used 4 encodes a short clip in a few seconds
            "-c:v", "libvpx-vp9", "-b:v", "0", "-crf", "32",
            "-deadline", "good", "-cpu-used", "4", "-row-mt", "1",
            "-c:a", "libopus", "-b:a", "128k",
        ]  # fmt: skip
    else:
        target = _unique(file.with_suffix(".ogg"))
        codecs = ["-vn", "-c:a", "libopus", "-b:a", "128k"]

    tmp = target.with_name(target.stem + ".part" + target.suffix)
    result = subprocess.run(
        [_ffmpeg(), "-hide_banner", "-loglevel", "error", "-y", "-i", str(file), *codecs, str(tmp)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        tmp.unlink(missing_ok=True)
        raise RuntimeError(f"Could not convert {file.name}: {result.stderr.strip()[-300:]}")
    tmp.replace(target)
    file.unlink()
    return target


def make_playable(file: Path) -> Path:
    """Returns the file itself if every target can play it, else its converted copy."""
    return convert(file) if needs_conversion(file) else file
