"""Updater tests, no internet needed: python -m unittest test_updater

A local HTTP server plays GitHub: the "latest release" JSON and the installer file.
"""

import hashlib
import http.server
import json
import tempfile
import threading
import time
import unittest
from pathlib import Path

from updater import DEFAULT_DOWNLOAD_PREFIX, UpdateError, Updater, is_newer, parse_version

INSTALLER = b"MZ" + b"installer bytes " * 70_000  # about 1.1 MB: several chunks


class FakeGitHub(http.server.ThreadingHTTPServer):
    """Serves /latest (JSON), /dl/<installer>, /dl/<installer>.sha256."""

    def __init__(self):
        super().__init__(("127.0.0.1", 0), self.Handler)
        self.release: dict = {}
        self.files: dict[str, bytes] = {}
        threading.Thread(target=self.serve_forever, args=(0.02,), daemon=True).start()

    @property
    def base(self) -> str:
        return f"http://127.0.0.1:{self.server_port}"

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            server: FakeGitHub = self.server  # type: ignore[assignment]
            if self.path == "/latest":
                body = json.dumps(server.release).encode()
            elif self.path.startswith("/dl/") and self.path[4:] in server.files:
                body = server.files[self.path[4:]]
            else:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass


def release(github: FakeGitHub, version="0.2.0", checksum="digest", data=INSTALLER, notes="Fixes") -> None:
    name = f"Slovonok-Setup-{version}.exe"
    sha = hashlib.sha256(data).hexdigest()
    asset = {"name": name, "size": len(data), "browser_download_url": f"{github.base}/dl/{name}"}
    assets = [asset]
    github.files = {name: data}
    if checksum == "digest":
        asset["digest"] = f"sha256:{sha}"
    elif checksum == "sidecar":
        assets.append({"name": name + ".sha256", "browser_download_url": f"{github.base}/dl/{name}.sha256"})
        github.files[name + ".sha256"] = f"{sha}  {name}\n".encode()
    github.release = {"tag_name": f"v{version}", "body": notes, "html_url": f"{github.base}/release", "assets": assets}


class UpdaterTest(unittest.TestCase):
    def setUp(self):
        self.github = FakeGitHub()
        self.dir = tempfile.TemporaryDirectory()
        self.launched: list[Path] = []
        self.restarted = threading.Event()
        self.events: list[dict] = []

    def tearDown(self):
        self.github.shutdown()
        self.github.server_close()
        self.dir.cleanup()

    def updater(self, current="0.1.0", can_install=True) -> Updater:
        u = Updater(
            current=current,
            download_dir=Path(self.dir.name),
            can_install=can_install,
            url=f"{self.github.base}/latest",
            publish=self.events.append,
            launcher=self.launched.append,
        )
        u.on_restart = self.restarted.set
        return u

    def wait_for(self, condition, timeout=10):
        end = time.time() + timeout
        while time.time() < end:
            if condition():
                return True
            time.sleep(0.02)
        return False


class TestVersions(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(parse_version("v1.2.3"), (1, 2, 3))
        self.assertEqual(parse_version("1.2.3"), (1, 2, 3))
        self.assertIsNone(parse_version("nightly"))
        self.assertIsNone(parse_version("1.2"))

    def test_compare_numbers_not_text(self):
        self.assertTrue(is_newer("0.10.0", "0.9.0"))  # as text "0.10.0" < "0.9.0"
        self.assertTrue(is_newer("1.0.0", "0.99.99"))
        self.assertFalse(is_newer("0.1.0", "0.1.0"))
        self.assertFalse(is_newer("0.0.9", "0.1.0"))
        self.assertFalse(is_newer("garbage", "0.1.0"))


class TestChecking(UpdaterTest):
    def test_newer_release_is_offered(self):
        release(self.github, "0.2.0", notes="New things")
        state = self.updater().check()
        self.assertTrue(state["available"])
        self.assertEqual((state["latest"], state["current"], state["notes"]), ("0.2.0", "0.1.0", "New things"))
        self.assertEqual(state["size"], len(INSTALLER))
        self.assertIsNone(state["error"])

    def test_same_or_older_release_is_not(self):
        release(self.github, "0.1.0")
        self.assertFalse(self.updater("0.1.0").check()["available"])
        self.assertFalse(self.updater("0.3.0").check()["available"])

    def test_offline_is_reported_not_raised(self):
        self.github.shutdown()
        self.github.server_close()  # nothing listens any more: the connection is refused at once
        state = self.updater().check()
        self.assertFalse(state["available"])
        self.assertTrue(state["error"])
        self.assertEqual(state["stage"], "idle")

    def test_unexpected_release_name(self):
        release(self.github, "0.2.0")
        self.github.release["tag_name"] = "nightly"
        self.assertIn("Unexpected release name", self.updater().check()["error"])

    def test_announced_once_per_version(self):
        release(self.github, "0.2.0")
        u, seen = self.updater(), []
        u.on_available.append(seen.append)
        u.check()
        u.check()
        self.assertEqual(seen, ["0.2.0"])

    def test_state_changes_are_published(self):
        release(self.github, "0.2.0")
        self.updater().check()
        stages = [e["update"]["stage"] for e in self.events if e["type"] == "update"]
        self.assertEqual(stages[0], "checking")
        self.assertEqual(stages[-1], "idle")


class TestInstalling(UpdaterTest):
    def install_and_wait(self, u: Updater) -> dict:
        u.install()
        self.assertTrue(self.wait_for(lambda: u.state()["stage"] != "downloading"))
        return u.state()

    def test_downloads_verifies_and_launches_the_installer(self):
        release(self.github, "0.2.0")
        u = self.updater()
        u.check()
        state = self.install_and_wait(u)
        self.assertEqual(state["stage"], "installing")
        self.assertTrue(self.restarted.wait(5))
        self.assertEqual(len(self.launched), 1)
        self.assertEqual(self.launched[0].name, "Slovonok-Setup-0.2.0.exe")
        self.assertEqual(self.launched[0].read_bytes(), INSTALLER)

    def test_checksum_from_a_sidecar_file(self):
        release(self.github, "0.2.0", checksum="sidecar")
        u = self.updater()
        u.check()
        self.assertEqual(self.install_and_wait(u)["stage"], "installing")

    def test_a_corrupted_download_is_refused_and_removed(self):
        release(self.github, "0.2.0")
        self.github.files["Slovonok-Setup-0.2.0.exe"] = INSTALLER[:-1] + b"X"  # not what was published
        u = self.updater()
        u.check()
        state = self.install_and_wait(u)
        self.assertIn("checksum", state["error"])
        self.assertEqual(self.launched, [])
        self.assertEqual(list(Path(self.dir.name).glob("Slovonok-Setup-*")), [])

    def test_no_published_checksum_means_no_install(self):
        release(self.github, "0.2.0", checksum="none")
        u = self.updater()
        u.check()
        state = self.install_and_wait(u)
        self.assertIn("no checksum", state["error"])
        self.assertEqual(self.launched, [])

    def test_a_development_run_never_installs(self):
        release(self.github, "0.2.0")
        u = self.updater(can_install=False)
        self.assertTrue(u.check()["available"])  # it can still report the news
        with self.assertRaises(UpdateError):
            u.install()
        self.assertEqual(self.launched, [])

    def test_nothing_to_install_without_a_newer_release(self):
        release(self.github, "0.1.0")
        u = self.updater("0.1.0")
        u.check()
        with self.assertRaises(UpdateError):
            u.install()

    def test_progress_is_reported(self):
        release(self.github, "0.2.0")
        u = self.updater()
        u.check()
        self.install_and_wait(u)
        progress = [e["update"]["progress"] for e in self.events if e["update"]["stage"] == "downloading"]
        self.assertTrue(progress)
        self.assertEqual(progress, sorted(progress))  # never goes backwards

    def test_with_the_real_repository_only_its_releases_are_downloaded(self):
        u = self.updater()
        u._restrict_downloads = True
        foreign = {"version": "0.2.0", "url": "https://example.com/Slovonok-Setup-0.2.0.exe", "sha256": "0" * 64}
        with self.assertRaises(UpdateError):
            u._download(foreign)
        self.assertTrue(DEFAULT_DOWNLOAD_PREFIX.startswith("https://github.com/"))

    def test_old_installers_are_cleaned_up(self):
        stale = Path(self.dir.name) / "Slovonok-Setup-0.0.1.exe"
        stale.write_bytes(b"old")
        self.updater()
        self.assertFalse(stale.exists())


if __name__ == "__main__":
    unittest.main()
