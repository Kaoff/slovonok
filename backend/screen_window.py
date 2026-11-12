"""Transparent, always-on-top, click-through window showing punishments on the streamer's screen.

Built with Qt WebEngine: unlike WebView2 (pywebview), it supports windows that are
both transparent per pixel and click-through.
"""

from __future__ import annotations

import sys

from PySide6.QtCore import Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QGuiApplication
from PySide6.QtWebEngineCore import QWebEngineSettings
from PySide6.QtWebEngineWidgets import QWebEngineView

from config import ScreenDisplay

TITLE = "Slovonok screen overlay"
WDA_EXCLUDEFROMCAPTURE = 0x11  # invisible to screen capture (Windows 10 2004+)
HWND_TOPMOST = -1
SWP_NOSIZE, SWP_NOMOVE, SWP_NOACTIVATE = 0x0001, 0x0002, 0x0010
KEEP_ON_TOP_INTERVAL = 2000  # ms


def _user32():
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    user32.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
    user32.GetAncestor.restype = wintypes.HWND
    user32.SetWindowDisplayAffinity.argtypes = [wintypes.HWND, wintypes.DWORD]
    user32.SetWindowDisplayAffinity.restype = wintypes.BOOL
    user32.GetWindowDisplayAffinity.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    user32.GetWindowDisplayAffinity.restype = wintypes.BOOL
    user32.SetWindowPos.argtypes = [
        wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.UINT
    ]
    user32.SetWindowPos.restype = wintypes.BOOL
    return user32


class ScreenWindow(QWebEngineView):
    # Emitted from any thread; the slot runs on the Qt thread, which owns the window.
    bring_to_front_requested = Signal()

    def __init__(self, settings: ScreenDisplay, url: str):
        super().__init__()
        self.bring_to_front_requested.connect(self.bring_to_front)
        # The taskbar and other "always on top" windows can end up above us
        # (e.g. after a click on the taskbar): take the top spot back regularly.
        self._keep_on_top = QTimer(self)
        self._keep_on_top.timeout.connect(self.bring_to_front)
        self._keep_on_top.start(KEEP_ON_TOP_INTERVAL)
        self.hide_from_capture = settings.hide_from_capture
        self.setWindowTitle(TITLE)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool  # no taskbar button, not in Alt+Tab
            | Qt.WindowType.WindowTransparentForInput  # mouse and keyboard go to the game
            | Qt.WindowType.WindowDoesNotAcceptFocus
            | Qt.WindowType.NoDropShadowWindowHint  # Windows draws a shadow around tool windows
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setStyleSheet("background: transparent")
        self.page().setBackgroundColor(Qt.GlobalColor.transparent)

        web = self.settings()
        web.setAttribute(QWebEngineSettings.WebAttribute.PlaybackRequiresUserGesture, False)
        web.setAttribute(QWebEngineSettings.WebAttribute.ShowScrollBars, False)

        screens = QGuiApplication.screens()
        screen = screens[settings.monitor] if 0 <= settings.monitor < len(screens) else QGuiApplication.primaryScreen()
        # One pixel short of the full screen: a window covering the whole monitor is treated
        # by Windows as a fullscreen app, which changes how the taskbar is drawn.
        g = screen.geometry()
        self.setGeometry(g.x(), g.y(), g.width(), g.height() - 1)
        print(f"Screen overlay on '{screen.name()}' ({g.width()}×{g.height()}, scale {screen.devicePixelRatio()})")
        self.load(QUrl(url))

    def showEvent(self, event):
        super().showEvent(event)
        if self.hide_from_capture and sys.platform == "win32":
            # Qt may still (re)create the native window right after showing it,
            # so apply once the event loop has settled, and once more a bit later.
            QTimer.singleShot(0, self._exclude_from_capture)
            QTimer.singleShot(1000, lambda: self._exclude_from_capture(report=True))

    def _hwnd(self, user32) -> int:
        GA_ROOT = 2
        return user32.GetAncestor(int(self.winId()), GA_ROOT)  # the top-level window

    def bring_to_front(self) -> None:
        """Puts the window back at the top of the "always on top" windows, without taking focus."""
        if sys.platform != "win32":
            self.raise_()
            return
        user32 = _user32()
        user32.SetWindowPos(
            self._hwnd(user32), HWND_TOPMOST, 0, 0, 0, 0, SWP_NOSIZE | SWP_NOMOVE | SWP_NOACTIVATE
        )

    def _exclude_from_capture(self, report: bool = False) -> None:
        import ctypes
        from ctypes import wintypes

        user32 = _user32()
        hwnd = self._hwnd(user32)
        if not user32.SetWindowDisplayAffinity(hwnd, WDA_EXCLUDEFROMCAPTURE):
            error = ctypes.get_last_error()
            print(f"⚠ Could not hide the screen overlay from capture (error {error}, needs Windows 10 2004+)")
            return
        if report:
            affinity = wintypes.DWORD()
            user32.GetWindowDisplayAffinity(hwnd, ctypes.byref(affinity))
            hidden = affinity.value == WDA_EXCLUDEFROMCAPTURE
            print(f"{'🙈' if hidden else '⚠'} Screen overlay hidden from capture: {hidden} (affinity {affinity.value:#x})")
