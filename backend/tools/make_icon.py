"""Draws the app icon (a bell, in the Cybercore colors) into assets/icon.ico and icon.png.

Run once from backend/ when the design changes (the generated files are committed):
    python tools/make_icon.py
No image library needed: Qt draws it, and the ICO container (PNG images inside) is written by hand.
"""

from __future__ import annotations

import struct
import sys
from pathlib import Path

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QGuiApplication, QImage, QPainter, QPainterPath, QPen

ASSETS = Path(__file__).resolve().parent.parent / "assets"
SIZES = (16, 24, 32, 48, 64, 128, 256)
CYAN, MAGENTA, BLACK = QColor("#00f0ff"), QColor("#ff2bd6"), QColor("#05060b")


def draw(size: int) -> QImage:
    image = QImage(size, size, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    p = QPainter(image)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    u = size / 100  # work on a 100x100 canvas

    # Dark rounded square with a cyan frame
    p.setBrush(QBrush(BLACK))
    p.setPen(QPen(CYAN, max(1.0, 4 * u)))
    p.drawRoundedRect(QRectF(4 * u, 4 * u, 92 * u, 92 * u), 16 * u, 16 * u)

    # The bell: a dome that flares out at the bottom
    bell = QPainterPath()
    bell.moveTo(QPointF(26 * u, 68 * u))
    bell.cubicTo(QPointF(32 * u, 60 * u), QPointF(32 * u, 50 * u), QPointF(33 * u, 42 * u))
    bell.cubicTo(QPointF(34 * u, 30 * u), QPointF(42 * u, 24 * u), QPointF(50 * u, 24 * u))
    bell.cubicTo(QPointF(58 * u, 24 * u), QPointF(66 * u, 30 * u), QPointF(67 * u, 42 * u))
    bell.cubicTo(QPointF(68 * u, 50 * u), QPointF(68 * u, 60 * u), QPointF(74 * u, 68 * u))
    bell.closeSubpath()
    p.setBrush(QBrush(QColor(0, 240, 255, 60)))
    p.setPen(QPen(CYAN, max(1.0, 5 * u), Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    p.drawPath(bell)

    # Top knob and clapper in magenta
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QBrush(MAGENTA))
    p.drawEllipse(QRectF(46 * u, 17 * u, 8 * u, 8 * u))
    p.drawEllipse(QRectF(43 * u, 72 * u, 14 * u, 14 * u))
    p.end()
    return image


def png_bytes(image: QImage) -> bytes:
    data = QByteArray()
    buffer = QBuffer(data)
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    image.save(buffer, "PNG")
    return bytes(data)


def write_ico(path: Path, images: dict[int, bytes]) -> None:
    """An ICO file whose images are PNGs (supported since Windows Vista)."""
    header = struct.pack("<HHH", 0, 1, len(images))
    offset = 6 + 16 * len(images)
    entries, payload = b"", b""
    for size, data in images.items():
        entries += struct.pack(
            "<BBBBHHII", 0 if size >= 256 else size, 0 if size >= 256 else size, 0, 0, 1, 32, len(data), offset
        )
        payload += data
        offset += len(data)
    path.write_bytes(header + entries + payload)


def main() -> None:
    app = QGuiApplication(sys.argv)  # Qt needs an application object to paint
    ASSETS.mkdir(exist_ok=True)
    images = {size: png_bytes(draw(size)) for size in SIZES}
    write_ico(ASSETS / "icon.ico", images)
    (ASSETS / "icon.png").write_bytes(images[256])
    print(f"Wrote {ASSETS / 'icon.ico'} ({len(images)} sizes) and icon.png")
    del app


if __name__ == "__main__":
    main()
