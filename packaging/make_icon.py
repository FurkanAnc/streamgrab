"""Uygulama simgesini uretir: streamgrab/assets/icon.ico

Kullanim:  .venv\\Scripts\\python.exe packaging\\make_icon.py
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QGuiApplication, QImage, QPainter, QPolygonF

TARGET = Path(__file__).resolve().parent.parent / "streamgrab" / "assets" / "icon.ico"
SIZE = 256


def main() -> None:
    _app = QGuiApplication([])
    image = QImage(SIZE, SIZE, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)

    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QBrush(QColor("#4f8cff")))
    painter.drawRoundedRect(QRectF(8, 8, 240, 240), 52, 52)

    # Asagi ok ve altinda alt cizgi: "indir"
    painter.setBrush(QBrush(QColor("#0a1020")))
    painter.drawRect(QRectF(106, 52, 44, 76))
    painter.drawPolygon(QPolygonF([QPointF(68, 118), QPointF(188, 118), QPointF(128, 182)]))
    painter.drawRoundedRect(QRectF(60, 192, 136, 20), 10, 10)
    painter.end()

    TARGET.parent.mkdir(parents=True, exist_ok=True)
    if not image.save(str(TARGET), "ICO"):
        raise SystemExit("simge yazilamadi")
    print(f"yazildi: {TARGET}")


if __name__ == "__main__":
    main()
