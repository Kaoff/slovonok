"""The desktop shell: the panel in its own window, the tray icon, one instance at a time, and the
screen window that follows the settings live. All of this runs on the Qt thread.

Nothing here imports server or engine: main.py wires them in (and imports them late, after the
packaged app's runtime has been configured).
"""

from __future__ import annotations

from typing import Callable

from PySide6.QtCore import QLocale, QObject, QSettings, QTimer, QUrl, Signal
from PySide6.QtGui import QAction, QGuiApplication, QIcon
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWebEngineCore import QWebEngineSettings
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QMenu, QSystemTrayIcon

from screen_window import ScreenWindow

TITLE = "Slovonok"
INSTANCE_NAME = "slovonok-single-instance"


# --- Texts of the shell (before the panel exists, so outside its i18n) ---------------------------

TEXTS = {
    "en": {
        "open": "Open Slovonok",
        "pause": "Pause listening",
        "resume": "Resume listening",
        "quit": "Quit",
        "listening": "listening",
        "paused": "paused",
        "idle": "not listening",
        "port": "Slovonok cannot start: port {port} is already used by another program.",
        "update": "Version {version} is available. Open the settings to install it.",
    },
    "fr": {
        "open": "Ouvrir Slovonok",
        "pause": "Mettre l'écoute en pause",
        "resume": "Reprendre l'écoute",
        "quit": "Quitter",
        "listening": "écoute en cours",
        "paused": "en pause",
        "idle": "pas d'écoute",
        "port": "Slovonok ne peut pas démarrer : le port {port} est déjà utilisé par un autre programme.",
        "update": "La version {version} est disponible. Ouvrez les réglages pour l'installer.",
    },
}


def text(key: str, language: str | None = None, **params) -> str:
    language = language or ("fr" if QGuiApplication.instance() and _system_is_french() else "en")
    return TEXTS.get(language, TEXTS["en"])[key].format(**params)


def _system_is_french() -> bool:
    return QLocale.system().language() == QLocale.Language.French


# --- One instance at a time ------------------------------------------------------------------------


class SingleInstance(QObject):
    """A second launch asks the first one to show its window, then exits."""

    show_requested = Signal()

    def __init__(self):
        super().__init__()
        self._server = QLocalServer(self)
        self._server.newConnection.connect(self._on_connection)

    @staticmethod
    def activate_running() -> bool:
        """True if another instance is running (it was asked to show its panel)."""
        socket = QLocalSocket()
        socket.connectToServer(INSTANCE_NAME)
        if not socket.waitForConnected(300):
            return False
        socket.write(b"show")
        socket.waitForBytesWritten(300)
        socket.disconnectFromServer()
        return True

    def listen(self) -> bool:
        QLocalServer.removeServer(INSTANCE_NAME)  # a crashed instance leaves its socket behind
        return self._server.listen(INSTANCE_NAME)

    def _on_connection(self) -> None:
        connection = self._server.nextPendingConnection()
        if connection:
            connection.readyRead.connect(self.show_requested.emit)
            connection.disconnected.connect(connection.deleteLater)


# --- The panel's window ------------------------------------------------------------------------------


class PanelWindow(QWebEngineView):
    """The config panel (the web app served locally) in a normal window.
    Closing it hides it: the app keeps listening from the tray."""

    def __init__(self, url: str, icon: QIcon):
        super().__init__()
        self.quitting = False
        self._settings = QSettings("Slovonok", "Slovonok")
        self.setWindowTitle(TITLE)
        self.setWindowIcon(icon)
        self.settings().setAttribute(QWebEngineSettings.WebAttribute.JavascriptCanAccessClipboard, True)
        self.resize(1280, 820)
        geometry = self._settings.value("panel/geometry")
        if geometry:
            self.restoreGeometry(geometry)
        self.load(QUrl(url))

    def show_panel(self) -> None:
        if self.isMinimized():
            self.showNormal()
        self.show()
        self.raise_()
        self.activateWindow()

    def closeEvent(self, event) -> None:
        self._settings.setValue("panel/geometry", self.saveGeometry())
        if self.quitting or not QSystemTrayIcon.isSystemTrayAvailable():
            event.accept()
        else:
            event.ignore()
            self.hide()


# --- Tray ---------------------------------------------------------------------------------------------


class Tray(QSystemTrayIcon):
    """Open the panel, pause/resume listening, quit."""

    def __init__(
        self,
        icon: QIcon,
        is_paused: Callable[[], bool],
        is_listening: Callable[[], bool],
        set_paused: Callable[[bool], None],
        on_open: Callable[[], None],
        on_quit: Callable[[], None],
    ):
        super().__init__(icon)
        self._is_paused, self._is_listening, self._set_paused = is_paused, is_listening, set_paused
        menu = QMenu()
        self._open = QAction(text("open"), menu)
        self._open.triggered.connect(on_open)
        self._pause = QAction(menu)
        self._pause.triggered.connect(lambda: self._set_paused(not self._is_paused()))
        quit_action = QAction(text("quit"), menu)
        quit_action.triggered.connect(on_quit)
        menu.addAction(self._open)
        menu.addAction(self._pause)
        menu.addSeparator()
        menu.addAction(quit_action)
        menu.aboutToShow.connect(self.refresh)
        self.setContextMenu(menu)
        self._menu = menu  # a QMenu without a parent is deleted if nobody keeps it
        self.activated.connect(
            lambda reason: on_open()
            if reason in (QSystemTrayIcon.ActivationReason.Trigger, QSystemTrayIcon.ActivationReason.DoubleClick)
            else None
        )
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.refresh)
        self._timer.start(3000)
        self.refresh()

    def refresh(self) -> None:
        paused = self._is_paused()
        self._pause.setText(text("resume" if paused else "pause"))
        state = "paused" if paused else "listening" if self._is_listening() else "idle"
        self.setToolTip(f"{TITLE} — {text(state)}")


# --- The screen window, kept in line with the settings --------------------------------------------------


class ScreenController(QObject):
    """Owns the transparent screen window. Changing the monitor, enabling or disabling it, or
    hiding it from capture takes effect at once: the window is recreated."""

    # Emitted from any thread (the engine's), handled on the Qt thread that owns the window
    config_changed = Signal(object)
    bring_to_front_requested = Signal()

    def __init__(self, url: str):
        super().__init__()
        self._url = url
        self._window: ScreenWindow | None = None
        self._key: tuple | None = None
        self.config_changed.connect(self.apply)
        self.bring_to_front_requested.connect(self._bring_to_front)

    def apply(self, config) -> None:
        screen = config.display.screen
        if not screen.enabled:
            self._close()
            return
        key = (screen.monitor, screen.hide_from_capture)
        if self._window is not None and key == self._key:
            return  # nothing that needs the window again (sound etc. are read by the page itself)
        self._close()
        self._window = ScreenWindow(screen, self._url)
        self._key = key
        self._window.show()

    def _close(self) -> None:
        if self._window is not None:
            self._window.close()
            self._window.deleteLater()
        self._window, self._key = None, None

    def _bring_to_front(self) -> None:
        if self._window is not None:
            self._window.bring_to_front()

    def close(self) -> None:
        self._close()


def screens_info() -> list[dict]:
    """The screens, as the panel's settings list them."""
    primary = QGuiApplication.primaryScreen()
    return [
        {
            "index": i,
            "name": s.name(),
            "width": s.geometry().width(),
            "height": s.geometry().height(),
            "primary": s == primary,
        }
        for i, s in enumerate(QGuiApplication.screens())
    ]

