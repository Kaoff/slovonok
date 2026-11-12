"""End-to-end test of install -> update -> relaunch -> uninstall with the real installers.

Usage (see RELEASING.md): python packaging/update_e2e.py <old installer> <new installer> <scratch dir>
The two installers are two builds of consecutive versions (bump backend/version.py temporarily,
run build.ps1 twice, keep both from packaging/output; don't commit the bump).
Nothing touches a real installation: the app installs to <scratch>/inst (per-user, silent), runs with
an isolated data dir and port, and the "GitHub" is a local HTTP server.
"""

import hashlib
import http.server
import json
import os
import shutil
import socket
import subprocess
import sys
import threading
import time
import urllib.request
import winreg
from pathlib import Path

OLD, NEW, SCRATCH = (Path(a) for a in sys.argv[1:4])
INST = SCRATCH / "inst"
DATA = SCRATCH / "data"
FAKE = SCRATCH / "fake"
PORT, FAKE_PORT = 8795, 8796
BASE = f"http://127.0.0.1:{PORT}"
APP_ID = "{DE448794-5C21-4A39-B724-8740863AF477}_is1"
UNINSTALL_KEY = rf"Software\Microsoft\Windows\CurrentVersion\Uninstall\{APP_ID}"

results = []


def check(name, ok, detail=""):
    results.append(bool(ok))
    print(f"{'OK  ' if ok else 'FAIL'} {name} {detail}", flush=True)


def get(path, timeout=5):
    with urllib.request.urlopen(BASE + path, timeout=timeout) as r:
        return json.load(r)


def post(path, body=None, timeout=15):
    req = urllib.request.Request(BASE + path, method="POST", data=json.dumps(body or {}).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def put(path, body):
    req = urllib.request.Request(BASE + path, method="PUT", data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.load(r)


def wait(predicate, timeout=60, step=0.5):
    end = time.time() + timeout
    while time.time() < end:
        try:
            value = predicate()
            if value:
                return value
        except Exception:
            pass
        time.sleep(step)
    return None


def registry_version():
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, UNINSTALL_KEY) as key:
            return winreg.QueryValueEx(key, "DisplayVersion")[0]
    except OSError:
        return None


def port_open(port=PORT):
    with socket.socket() as s:
        return s.connect_ex(("127.0.0.1", port)) == 0


def kill_installed_app():
    subprocess.run(
        ["powershell.exe", "-NoProfile", "-Command",
         f"Get-Process | Where-Object {{ $_.Path -like '{INST}\\*' }} | Stop-Process -Force -ErrorAction SilentlyContinue"],
        capture_output=True,
    )


def run_installer(path: Path, *extra):
    log = SCRATCH / f"{path.stem}.log"
    return subprocess.run([str(path), "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", f"/DIR={INST}", f"/LOG={log}", *extra], timeout=900)


# --- A local "GitHub": the latest release is the NEW installer ---------------------------------------
FAKE.mkdir(parents=True, exist_ok=True)
new_bytes_hash = hashlib.sha256(NEW.read_bytes()).hexdigest()
new_version = NEW.stem.removeprefix("Slovonok-Setup-")
shutil.copy(NEW, FAKE / NEW.name)
release = {
    "tag_name": f"v{new_version}",
    "body": "End-to-end test release",
    "html_url": "http://example.invalid/release",
    "assets": [{
        "name": NEW.name,
        "size": NEW.stat().st_size,
        "browser_download_url": f"http://127.0.0.1:{FAKE_PORT}/dl/{NEW.name}",
        "digest": f"sha256:{new_bytes_hash}",
    }],
}


class Handler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/latest":
            body = json.dumps(release).encode()
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif self.path.startswith("/dl/"):
            self.path = "/" + self.path[4:]
            super().do_GET()
        else:
            self.send_error(404)

    def log_message(self, *a):
        pass


Handler.directory = str(FAKE)
server = http.server.ThreadingHTTPServer(("127.0.0.1", FAKE_PORT), lambda *a, **k: Handler(*a, directory=str(FAKE), **k))
threading.Thread(target=server.serve_forever, daemon=True).start()

env = dict(os.environ, SLOVONOK_PORT=str(PORT), SLOVONOK_DATA_DIR=str(DATA), SLOVONOK_NO_LISTENING="1",
           SLOVONOK_UPDATE_URL=f"http://127.0.0.1:{FAKE_PORT}/latest")

try:
    shutil.rmtree(INST, ignore_errors=True)
    shutil.rmtree(DATA, ignore_errors=True)
    check("nothing registered before", registry_version() is None, f"({registry_version()})")

    # 1. Fresh install of the old version, silently
    code = run_installer(OLD, "/NORELAUNCH=1").returncode
    exe = INST / "Slovonok.exe"
    check("old installer succeeds", code == 0 and exe.is_file(), f"(code {code})")
    old_version = OLD.stem.removeprefix("Slovonok-Setup-")
    check("registered with the old version", registry_version() == old_version, f"({registry_version()})")

    # A stale file in _internal, as a previous version's leftover
    stale = INST / "_internal" / "stale-from-previous-version.dll"
    stale.write_bytes(b"x")

    # 2. Start the installed app
    app = subprocess.Popen([str(exe)], env=env, cwd=INST)
    state = wait(lambda: get("/api/update"), 60)
    check("installed app starts", bool(state))
    check("it is the packaged app, old version", bool(state) and state["current"] == old_version and state["can_install"] is True, str(state and (state["current"], state["can_install"])))

    # User data that must survive the update
    config = get("/api/config")
    config["words"].append({"id": "w-persist", "word": "persist-me", "mode": "exact", "enabled": True, "count": 0,
                            "punishments": {"strategy": "all", "ids": []}})
    put("/api/config", config)
    check("user data written in the data dir", (DATA / "config.json").is_file())

    # 3. Look for updates, then install
    found = post("/api/update/check")
    check("update found", found["available"] and found["latest"] == new_version, f"({found['latest']}, error={found['error']})")
    post("/api/update/install")
    gone = wait(lambda: not port_open(), 180)
    check("app quits for the installer", bool(gone))

    # 4. The installer replaces the files and relaunches the app
    relaunched = wait(lambda: get("/api/update")["current"] == new_version and get("/api/update"), 300, 1)
    check("app relaunched on the new version", bool(relaunched), str(relaunched and relaunched["current"]))
    check("registered with the new version", registry_version() == new_version, f"({registry_version()})")
    check("stale file from the old version removed", not stale.exists())
    check("user data survived", any(w["word"] == "persist-me" for w in get("/api/config")["words"]))
    check("no update offered any more", relaunched and not relaunched["available"])
finally:
    kill_installed_app()
    time.sleep(2)
    # 5. Uninstall
    uninstaller = INST / "unins000.exe"
    if uninstaller.is_file():
        subprocess.run([str(uninstaller), "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART"], timeout=300)
        time.sleep(3)
    check("uninstall removes the registration", registry_version() is None, f"({registry_version()})")
    check("uninstall removes the program", not (INST / "Slovonok.exe").exists())
    check("uninstall silently keeps the user's data", (DATA / "config.json").is_file())
    server.shutdown()
    shutil.rmtree(INST, ignore_errors=True)
    shutil.rmtree(DATA, ignore_errors=True)

print("ALL OK" if all(results) else "FAILURES", flush=True)
sys.exit(0 if all(results) else 1)
