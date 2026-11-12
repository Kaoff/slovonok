"""Desktop app entry point: local server, panel window, tray icon, on-screen overlay window.

Run: python main.py          (Ctrl+C in the terminal to quit)
     python main.py --background    start hidden in the tray
     Slovonok.exe --smoke report.json    self-test of a packaged build (see smoke.py)
"""

from __future__ import annotations

import argparse
import os
import signal
import socket
import sys
import threading
import time

import paths

# Packaged app: bundled espeak, output to a log file. Before phonemizer or logging are used.
paths.configure_runtime()

# Qt WebEngine (Chromium) logs harmless internal errors, e.g. when it probes the
# Windows hardware video encoders at startup. Only show fatal errors.
os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--log-level=3")

import uvicorn  # noqa: E402
from PySide6.QtCore import QTimer, QUrl  # noqa: E402
from PySide6.QtGui import QIcon  # noqa: E402
from PySide6.QtWidgets import QApplication, QMessageBox, QSystemTrayIcon  # noqa: E402

import shell  # noqa: E402
from version import __version__  # noqa: E402

HOST = "127.0.0.1"
PORT = int(os.environ.get("SLOVONOK_PORT", "8765"))  # the override is for tests: OBS URLs assume 8765


def hold_app_mutex() -> object:
    """A named mutex that exists while the app runs: the installer and uninstaller check it
    (AppMutex in installer.iss) and ask to close the app first. Keep the returned handle alive."""
    if sys.platform != "win32":
        return None
    import ctypes

    return ctypes.windll.kernel32.CreateMutexW(None, False, "Slovonok.SingleInstance")


def port_is_taken() -> bool:
    with socket.socket() as probe:
        return probe.connect_ex((HOST, PORT)) == 0


def wait_for_server(timeout: float = 20) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with socket.create_connection((HOST, PORT), timeout=0.2):
                return
        except OSError:
            time.sleep(0.1)
    raise RuntimeError(f"The local server did not start on port {PORT}")


def smoke_webengine(qt_app: QApplication, report: list[dict], done) -> None:
    """The one check that needs the Qt event loop: can the web engine load the panel?"""
    from PySide6.QtWebEngineWidgets import QWebEngineView

    view = QWebEngineView()
    outcome = {"name": "web engine (panel window)", "ok": False, "detail": "timeout"}

    finished = []

    def finish() -> None:
        if finished:
            return
        finished.append(True)
        report.append(outcome)
        view.deleteLater()
        done()

    attempts = {"left": 40}

    def check_rendered() -> None:
        # The panel is a single-page app: its text only exists once its scripts have run
        def got_text(text) -> None:
            if text and len(text) > 20:
                outcome.update(ok=True, detail=f"{len(text)} characters of text rendered")
                return finish()
            attempts["left"] -= 1
            if attempts["left"] <= 0:
                outcome["detail"] = "the panel loaded but rendered nothing"
                return finish()
            QTimer.singleShot(500, check_rendered)

        view.page().runJavaScript("document.body ? document.body.innerText : ''", got_text)

    def loaded(ok: bool) -> None:
        if not ok:
            outcome["detail"] = "the panel did not load"
            return finish()
        check_rendered()

    view.loadFinished.connect(loaded)
    view.load(QUrl(f"http://{HOST}:{PORT}/"))
    QTimer.singleShot(60_000, finish)  # no-op if it already finished


def main() -> int:
    parser = argparse.ArgumentParser(description="Slovonok")
    parser.add_argument("--background", action="store_true", help="start in the tray, panel hidden")
    parser.add_argument("--smoke", metavar="REPORT", help="self-test, writes a JSON report, then quits")
    args, qt_args = parser.parse_known_args()

    qt_app = QApplication([sys.argv[0], *qt_args])
    qt_app.setApplicationName("Slovonok")
    qt_app.setApplicationVersion(__version__)
    qt_app.setQuitOnLastWindowClosed(False)  # closing the panel keeps the app in the tray
    icon = QIcon(str(paths.ICON_FILE))
    qt_app.setWindowIcon(icon)

    mutex = hold_app_mutex()  # noqa: F841 - released when the process ends
    single = shell.SingleInstance()
    if not args.smoke:
        if single.activate_running():
            return 0  # the running instance shows its panel
        single.listen()
    if port_is_taken():
        message = shell.text("port", port=PORT)
        if args.smoke:
            print(message, file=sys.stderr)
        else:
            QMessageBox.critical(None, shell.TITLE, message)
        return 1

    # Late import: it creates the engine, which needs the runtime configured above
    from server import app, engine, updater

    server = uvicorn.Server(uvicorn.Config(app, host=HOST, port=PORT, log_level="warning"))
    server_thread = threading.Thread(target=server.run, daemon=True, name="server")
    server_thread.start()
    wait_for_server()
    print(f"Slovonok {__version__} — OBS overlay: http://localhost:{PORT}/overlay/")

    engine.screens = shell.screens_info()
    qt_app.screenAdded.connect(lambda _: setattr(engine, "screens", shell.screens_info()))
    qt_app.screenRemoved.connect(lambda _: setattr(engine, "screens", shell.screens_info()))

    exit_code = 0
    if args.smoke:
        import smoke

        report = smoke.run_checks(f"http://{HOST}:{PORT}", engine)
        smoke_webengine(qt_app, report, qt_app.quit)
        qt_app.exec()
        exit_code = smoke.write_report(args.smoke, report)
    else:
        exit_code = run_app(qt_app, single, engine, updater, icon, args)

    # Release the microphone and the port before leaving (the installer replaces our files)
    engine.stop_listening()
    server.should_exit = True
    server_thread.join(timeout=5)
    return exit_code


def run_app(qt_app: QApplication, single: shell.SingleInstance, engine, updater, icon: QIcon, args) -> int:
    panel = shell.PanelWindow(f"http://{HOST}:{PORT}/", icon)
    screen = shell.ScreenController(f"http://{HOST}:{PORT}/overlay/?target=screen")
    # Settings changes (monitor, enabled, hidden from capture) apply live; a punishment puts the window on top
    engine.config_listeners.append(screen.config_changed.emit)
    engine.before_punishment.append(screen.bring_to_front_requested.emit)
    screen.apply(engine.store.read())

    def quit_app() -> None:
        panel.quitting = True
        qt_app.quit()

    tray = None
    if QSystemTrayIcon.isSystemTrayAvailable():
        tray = shell.Tray(
            icon,
            is_paused=lambda: engine.paused,
            is_listening=lambda: bool(engine.listener and engine.listener.is_alive()),
            set_paused=engine.set_paused,
            on_open=panel.show_panel,
            on_quit=quit_app,
        )
        tray.show()
    single.show_requested.connect(panel.show_panel)
    # Windows is shutting down or logging off: leave instead of hiding to the tray
    qt_app.commitDataRequest.connect(lambda *_: setattr(panel, "quitting", True))

    # Updates: the updater runs in worker threads, the bridge hands its news to the Qt thread
    bridge = shell.UpdateBridge()
    updater.on_available.append(bridge.available.emit)
    updater.on_restart = bridge.restart.emit
    bridge.restart.connect(quit_app)
    if tray:
        bridge.available.connect(lambda version: tray.showMessage(shell.TITLE, shell.text("update", version=version)))
    if paths.FROZEN or os.environ.get("SLOVONOK_AUTO_UPDATE_CHECK") == "1":  # a development run doesn't poll GitHub
        updater.start_background_checks()
    if not args.background or tray is None:
        panel.show_panel()

    # Qt's event loop hides Ctrl+C from Python: quit explicitly, and wake Python up regularly.
    for name in ("SIGINT", "SIGBREAK"):  # SIGBREAK: Ctrl+Break and a closing console, Windows only
        if hasattr(signal, name):
            signal.signal(getattr(signal, name), lambda *_: quit_app())
    timer = QTimer()
    timer.timeout.connect(lambda: None)
    timer.start(250)

    qt_app.exec()
    screen.close()
    if tray:
        tray.hide()
    return 0


if __name__ == "__main__":
    sys.exit(main())
