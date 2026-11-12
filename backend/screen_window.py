"""Transparent, always-on-top, click-through window showing punishments on the streamer's screen.

Built with Qt WebEngine: unlike WebView2 (pywebview), it supports windows that are
both transparent per pixel and click-through.
"""

from __future__ import annotations

import sys

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtWebEngineCore import QWebEngineSettings
from PySide6.QtWebEngineWidgets import QWebEngineView

from config import ScreenDisplay

TITLE = "forbidden-word screen overlay"
WDA_EXCLUDEFROMCAPTURE = 0x11  # invisible to screen capture (Windows 10 2004+)


class ScreenWindow(QWebEngineView):
    def __init__(self, settings: ScreenDisplay, url: str):
        super().__init__()
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
            import ctypes

            hwnd = int(self.winId())
            if not ctypes.windll.user32.SetWindowDisplayAffinity(hwnd, WDA_EXCLUDEFROMCAPTURE):
                print("⚠ Could not hide the screen overlay from capture (requires Windows 10 2004+)")
