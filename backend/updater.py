"""Automatic updates from GitHub releases.

Flow: look at the latest release (drafts and pre-releases excluded by GitHub's "latest" endpoint),
and if its version is newer than ours, offer it. Installing downloads the release's installer
(Slovonok-Setup-<version>.exe), checks its SHA-256, starts it silently and quits the app so it
can replace the files; the installer then relaunches the app.

Rules that keep it safe:
- A development run (not packaged) never downloads or installs anything.
- An installer without a published checksum is refused.
- With the default repository, the download must come from that repository's releases.
- The check never blocks the app and a failure (offline...) is just reported.

The release source can be changed for tests with SLOVONOK_UPDATE_URL (the API's "latest" JSON).
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import threading
import time
import urllib.request
from pathlib import Path
from typing import Callable

REPOSITORY = "Kaoff/slovonok"
DEFAULT_URL = f"https://api.github.com/repos/{REPOSITORY}/releases/latest"
DEFAULT_DOWNLOAD_PREFIX = f"https://github.com/{REPOSITORY}/releases/download/"
INSTALLER_NAME = re.compile(r"^Slovonok-Setup-(\d+\.\d+\.\d+)\.exe$")
TIMEOUT = 15  # seconds, for each network request
CHECK_EVERY = 6 * 3600  # while the app runs (a stream can last long)
INSTALLER_ARGS = ["/SILENT", "/SUPPRESSMSGBOXES", "/NORESTART"]
USER_AGENT = "Slovonok-updater"


def parse_version(text: str) -> tuple[int, int, int] | None:
    """"v1.2.3" or "1.2.3" -> (1, 2, 3). None if it isn't a plain version."""
    match = re.match(r"^v?(\d+)\.(\d+)\.(\d+)$", text.strip())
    return tuple(int(part) for part in match.groups()) if match else None  # type: ignore[return-value]


def is_newer(candidate: str, current: str) -> bool:
    a, b = parse_version(candidate), parse_version(current)
    return a is not None and b is not None and a > b


def _get(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
        return response.read()


def installer_command(installer: Path, pid: int) -> list[str]:
    """PowerShell waits for the app (pid) to be gone, then starts the installer: the installer
    refuses to run while the app is open, and closing it takes a few seconds."""
    quoted = str(installer).replace("'", "''")
    arguments = ",".join(f"'{a}'" for a in INSTALLER_ARGS)
    script = (
        f"Wait-Process -Id {pid} -Timeout 90 -ErrorAction SilentlyContinue; "
        f"Start-Process -FilePath '{quoted}' -ArgumentList {arguments}"
    )
    return ["powershell.exe", "-NoProfile", "-NonInteractive", "-WindowStyle", "Hidden", "-Command", script]


def launch_installer(installer: Path, pid: int | None = None) -> None:
    """Starts, independently of the app, what will run the installer once the app (`pid`) has quit.

    Not DETACHED_PROCESS: PowerShell needs a console, and without one it exits at once without
    running anything (found the hard way). CREATE_NO_WINDOW gives it a hidden one, and works from
    a windowed app that has no console of its own."""
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    subprocess.Popen(
        installer_command(installer, pid if pid is not None else os.getpid()),
        creationflags=flags,
        close_fds=True,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


class UpdateError(Exception):
    pass


class Updater:
    def __init__(
        self,
        current: str,
        download_dir: Path,
        can_install: bool,
        url: str | None = None,
        publish: Callable[[dict], None] | None = None,
        launcher: Callable[[Path], None] = launch_installer,
    ):
        self.current = current
        self.download_dir = download_dir
        self.can_install = can_install  # False for a development run
        self.url = url or os.environ.get("SLOVONOK_UPDATE_URL") or DEFAULT_URL
        # With the real repository, only its own releases may be downloaded
        self._restrict_downloads = self.url == DEFAULT_URL
        self._publish = publish or (lambda state: None)
        self._launcher = launcher
        self._lock = threading.RLock()
        self._release: dict | None = None  # what the last check found: version, notes, url, size, sha256
        self._stage = "idle"  # idle | checking | downloading | installing
        self._progress = 0.0
        self._error: str | None = None
        self._last_checked: float | None = None
        # Called from a worker thread: the app announces the update / quits to let the installer work
        self.on_available: list[Callable[[str], None]] = []
        self.on_restart: Callable[[], None] | None = None
        self._announced: set[str] = set()
        self._clean_download_dir()

    # --- State ---------------------------------------------------------------------------------

    def state(self) -> dict:
        with self._lock:
            release = self._release or {}
            return {
                "current": self.current,
                "latest": release.get("version"),
                "available": bool(release) and is_newer(release["version"], self.current),
                "notes": release.get("notes", ""),
                "size": release.get("size"),
                "page_url": release.get("page_url"),
                "stage": self._stage,
                "progress": round(self._progress, 3),
                "error": self._error,
                "last_checked": self._last_checked,
                "can_install": self.can_install,
            }

    def _set(self, **changes) -> None:
        with self._lock:
            for key, value in changes.items():
                setattr(self, f"_{key}", value)
            state = self.state()
        self._publish({"type": "update", "update": state})

    # --- Checking ------------------------------------------------------------------------------

    def check(self) -> dict:
        """Asks the release source. Blocking (a few seconds at most); errors end up in the state."""
        with self._lock:
            if self._stage in ("checking", "downloading", "installing"):
                return self.state()
        self._set(stage="checking", error=None)
        try:
            release = self._fetch_latest()
            self._set(stage="idle", release=release, last_checked=time.time())
        except Exception as e:  # noqa: BLE001 - offline, rate limit, bad JSON...: reported, never fatal
            self._set(stage="idle", error=f"{type(e).__name__}: {e}", last_checked=time.time())
            return self.state()
        state = self.state()
        if state["available"]:
            self._announce(state["latest"])
        return state

    def _fetch_latest(self) -> dict:
        data = json.loads(_get(self.url))
        version = str(data.get("tag_name", "")).lstrip("v")
        if parse_version(version) is None:
            raise UpdateError(f"Unexpected release name: {data.get('tag_name')!r}")
        assets = data.get("assets") or []
        installer = next((a for a in assets if INSTALLER_NAME.match(a.get("name", ""))), None)
        release = {
            "version": version,
            "notes": data.get("body") or "",
            "page_url": data.get("html_url"),
            "url": None,
            "size": None,
            "sha256": None,
        }
        if installer:
            release.update(url=installer["browser_download_url"], size=installer.get("size"))
            release["sha256"] = self._published_checksum(installer, assets)
        return release

    @staticmethod
    def _published_checksum(installer: dict, assets: list[dict]) -> str | None:
        """The SHA-256 GitHub computed (asset "digest"), or the one published as <installer>.sha256."""
        digest = str(installer.get("digest") or "")
        if digest.startswith("sha256:"):
            return digest.removeprefix("sha256:").lower()
        sidecar = next((a for a in assets if a.get("name") == installer["name"] + ".sha256"), None)
        if sidecar:
            match = re.match(r"\s*([0-9a-fA-F]{64})", _get(sidecar["browser_download_url"]).decode("utf-8", "replace"))
            if match:
                return match.group(1).lower()
        return None

    def _announce(self, version: str) -> None:
        if version in self._announced:
            return
        self._announced.add(version)
        for callback in list(self.on_available):
            try:
                callback(version)
            except Exception as e:  # noqa: BLE001
                print(f"⚠ Update notice failed: {e}")

    def start_background_checks(self, first_delay: float = 8.0) -> None:
        """Checks soon after the start, then regularly."""

        def loop() -> None:
            time.sleep(first_delay)
            while True:
                self.check()
                time.sleep(CHECK_EVERY)

        threading.Thread(target=loop, daemon=True, name="updates").start()

    # --- Installing ----------------------------------------------------------------------------

    def install(self) -> dict:
        """Downloads and starts the installer in the background (the state shows the progress)."""
        with self._lock:
            if not self.can_install:
                raise UpdateError("Updates are only installed by the packaged app")
            release = self._release
            if not release or not is_newer(release["version"], self.current):
                raise UpdateError("No newer version to install")
            if self._stage in ("downloading", "installing"):
                return self.state()
            self._stage, self._progress, self._error = "downloading", 0.0, None
        self._set()
        threading.Thread(target=self._download_and_install, args=(release,), daemon=True, name="update").start()
        return self.state()

    def _download_and_install(self, release: dict) -> None:
        try:
            installer = self._download(release)
            self._set(stage="installing", progress=1.0)
            self._launcher(installer)
            if self.on_restart:
                self.on_restart()
        except Exception as e:  # noqa: BLE001
            self._set(stage="idle", progress=0.0, error=f"{type(e).__name__}: {e}")

    def _download(self, release: dict) -> Path:
        url, expected = release.get("url"), release.get("sha256")
        if not url:
            raise UpdateError("This release has no installer")
        if not expected:
            raise UpdateError("This release publishes no checksum for its installer: not installing it")
        if self._restrict_downloads and not url.startswith(DEFAULT_DOWNLOAD_PREFIX):
            raise UpdateError(f"Refusing to download from {url}")

        self.download_dir.mkdir(parents=True, exist_ok=True)
        self._clean_download_dir()
        target = self.download_dir / f"Slovonok-Setup-{release['version']}.exe"
        partial = target.with_suffix(".exe.part")
        digest, received, total = hashlib.sha256(), 0, int(release.get("size") or 0)
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        last_report = 0.0
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response, partial.open("wb") as out:
            total = total or int(response.headers.get("Content-Length") or 0)
            while chunk := response.read(1 << 20):
                out.write(chunk)
                digest.update(chunk)
                received += len(chunk)
                if total and time.monotonic() - last_report > 0.25:
                    last_report = time.monotonic()
                    self._set(progress=min(received / total, 0.99))
        if digest.hexdigest() != expected.lower():
            partial.unlink(missing_ok=True)
            raise UpdateError("The downloaded installer does not match its published checksum")
        partial.replace(target)
        return target

    def _clean_download_dir(self) -> None:
        """Old installers and interrupted downloads."""
        if self.download_dir.is_dir():
            for file in self.download_dir.glob("Slovonok-Setup-*"):
                file.unlink(missing_ok=True)
