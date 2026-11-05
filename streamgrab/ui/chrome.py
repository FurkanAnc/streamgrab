"""Tema disinda kalan pencere ayrintilari: ikonlar, baslik cubugu, kapak resmi."""

from __future__ import annotations

import ctypes
import sys

from PySide6.QtCore import QByteArray, QRectF, QSize, Qt
from PySide6.QtGui import QIcon, QPainter, QPainterPath, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QWidget

from . import theme

_PATHS = {
    "download": '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M7 10l5 5 5-5M12 15V3"/>',
    "plus": '<path d="M12 5v14M5 12h14"/>',
    "list": '<path d="M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01"/>',
    "clock": '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    "settings": '<path d="M4 21v-7M4 10V3M12 21v-9M12 8V3M20 21v-5M20 12V3M1 14h6M9 8h6M17 16h6"/>',
    "pause": '<path d="M8 5v14M16 5v14"/>',
    "play": '<path d="M7 4.5v15l13-7.5z"/>',
    "x": '<path d="M18 6 6 18M6 6l12 12"/>',
    "folder": '<path d="M3 7a2 2 0 0 1 2-2h4l2 3h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>',
    "retry": '<path d="M21 12a9 9 0 1 1-2.6-6.4L21 8M21 3v5h-5"/>',
    "paste": '<path d="M9 4H7a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V6a2 2 0 0 0-2-2h-2M9 3h6v3H9z"/>',
    "clean": '<path d="M3 6h18M8 6V4h8v2M6 6l1 15h10l1-15M10 11v6M14 11v6"/>',
    "link": (
        '<path d="M10 14a5 5 0 0 0 7 0l3-3a5 5 0 0 0-7-7l-1 1"/>'
        '<path d="M14 10a5 5 0 0 0-7 0l-3 3a5 5 0 0 0 7 7l1-1"/>'
    ),
    "inbox": (
        '<path d="M22 12h-6l-2 3h-4l-2-3H2"/>'
        '<path d="M5.5 5 2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.5-7z"/>'
    ),
}


def _svg(name: str, color: str, weight: float) -> QByteArray:
    return QByteArray(
        (
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
            f'stroke="{color}" stroke-width="{weight}" stroke-linecap="round" '
            f'stroke-linejoin="round">{_PATHS[name]}</svg>'
        ).encode("utf-8")
    )


def icon_pixmap(name: str, color: str = theme.TEXT_MUTED, size: int = 18, weight: float = 2) -> QPixmap:
    """Yuksek DPI ekranlarda keskin kalsin diye 3 kat buyuk cizilir."""
    pixmap = QPixmap(size * 3, size * 3)
    pixmap.fill(Qt.GlobalColor.transparent)
    pixmap.setDevicePixelRatio(3)
    painter = QPainter(pixmap)
    QSvgRenderer(_svg(name, color, weight)).render(painter, QRectF(0, 0, size, size))
    painter.end()
    return pixmap


def icon(name: str, color: str = theme.TEXT_MUTED, checked_color: str = "") -> QIcon:
    result = QIcon(icon_pixmap(name, color))
    result.addPixmap(icon_pixmap(name, theme.TEXT), QIcon.Mode.Active)
    if checked_color:
        result.addPixmap(icon_pixmap(name, checked_color), QIcon.Mode.Normal, QIcon.State.On)
    return result


ICON_SIZE = QSize(18, 18)


def rounded_thumbnail(source: QPixmap, size: QSize, ratio: float, radius: float = 10) -> QPixmap:
    """Kapak resmini oranini bozmadan kirpar, koselerini yuvarlar."""
    width, height = int(size.width() * ratio), int(size.height() * ratio)
    scaled = source.scaled(
        width,
        height,
        Qt.AspectRatioMode.KeepAspectRatioByExpanding,
        Qt.TransformationMode.SmoothTransformation,
    )
    result = QPixmap(width, height)
    result.fill(Qt.GlobalColor.transparent)

    painter = QPainter(result)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    path = QPainterPath()
    path.addRoundedRect(QRectF(0, 0, width, height), radius * ratio, radius * ratio)
    painter.setClipPath(path)
    painter.drawPixmap((width - scaled.width()) // 2, (height - scaled.height()) // 2, scaled)
    painter.end()

    result.setDevicePixelRatio(ratio)
    return result


def apply_dark_titlebar(widget: QWidget) -> None:
    """Windows baslik cubugunu temaya uydurur (eski surumler yok sayar)."""
    if sys.platform != "win32":
        return
    try:
        hwnd = int(widget.winId())
        dwm = ctypes.windll.dwmapi
        dark = ctypes.c_int(1)
        dwm.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(dark), ctypes.sizeof(dark))
        # COLORREF 0x00BBGGRR: theme.BG
        caption = ctypes.c_int(0x0015110F)
        dwm.DwmSetWindowAttribute(hwnd, 35, ctypes.byref(caption), ctypes.sizeof(caption))
    except (AttributeError, OSError):  # kozmetik
        pass
