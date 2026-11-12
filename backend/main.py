"""Desktop app entry point: local server + on-screen overlay window.

Run: python main.py   (Ctrl+C in the terminal to quit)
"""

from __future__ import annotations

import os
import signal
import socket
import sys
import threading
import time

# Qt WebEngine (Chromium) logs harmless internal errors, e.g. when it probes the
# Windows hardware video encoders at startup. Only show fatal errors.
os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--log-level=3")

import uvicorn
from PySide6.QtCore import QTimer
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QApplication

from screen_window import ScreenWindow
from server import HOST, PORT, app, engine


def run_server() -> None:
    uvicorn.Server(uvicorn.Config(app, host=HOST, port=PORT, log_level="warning")).run()


def wait_for_server(timeout: float = 10) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with socket.create_connection((HOST, PORT), timeout=0.2):
                return
        except OSError:
            time.sleep(0.1)
    raise RuntimeError(f"The local server did not start on port {PORT}")


def main() -> None:
    server_thread = threading.Thread(target=run_server, daemon=True, name="server")
    server_thread.start()
    wait_for_server()
    print(f"OBS overlay: http://localhost:{PORT}/overlay/")

    screen = engine.store.read().display.screen
    if not screen.enabled:
        server_thread.join()
        return

    qt_app = QApplication(sys.argv)
    primary = QGuiApplication.primaryScreen()
    engine.screens = [
        {
            "index": i,
            "name": s.name(),
            "width": s.geometry().width(),
            "height": s.geometry().height(),
            "primary": s == primary,
        }
        for i, s in enumerate(QGuiApplication.screens())
    ]
    window = ScreenWindow(screen, f"http://{HOST}:{PORT}/overlay/?target=screen")
    window.show()
    # Right before a punishment plays, put the window back above everything (taskbar included).
    engine.before_punishment.append(window.bring_to_front_requested.emit)

    # Qt's event loop hides Ctrl+C from Python: quit explicitly, and wake Python up regularly.
    signal.signal(signal.SIGINT, lambda *_: qt_app.quit())
    timer = QTimer()
    timer.timeout.connect(lambda: None)
    timer.start(250)

    qt_app.exec()


if __name__ == "__main__":
    main()
