"""Tray ikonkalarni programmatik yaratish.

macOS menu bar va Windows system tray uchun mos o'lchamda
yashil (good), qizil (bad), sariq (idle) doira ikonkalar.
"""

from PySide6.QtGui import QIcon, QPixmap, QPainter, QColor, QBrush, QPen
from PySide6.QtCore import Qt, QRect


def _create_circle_pixmap(
    color: str,
    size: int = 64,
    border_color: str = "#ffffff",
    border_width: int = 2,
) -> QPixmap:
    """Rangli doira shaklidagi pixmap yaratadi."""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    # Tashqi border
    pen = QPen(QColor(border_color), border_width)
    painter.setPen(pen)
    painter.setBrush(QBrush(QColor(color)))

    margin = border_width
    rect = QRect(margin, margin, size - 2 * margin, size - 2 * margin)
    painter.drawEllipse(rect)

    painter.end()
    return pixmap


def create_tray_icon(status: str) -> QIcon:
    """Holat bo'yicha tray icon yaratadi.

    status: "good" | "bad" | "idle" | "off"
    """
    colors = {
        "good": "#2ecc71",   # yashil
        "bad": "#e74c3c",    # qizil
        "idle": "#f39c12",   # sariq
        "off": "#95a5a6",    # kulrang
    }
    color = colors.get(status, colors["off"])

    # macOS menu bar uchun 22x22 kerak, biz 64 yaratib Qt scale qiladi
    pixmap = _create_circle_pixmap(color, size=64, border_color="#2c3e50", border_width=3)
    return QIcon(pixmap)


# Cache — har safar qayta yaratmaslik uchun
_icon_cache: dict[str, QIcon] = {}


def get_tray_icon(status: str) -> QIcon:
    """Cached tray icon olish."""
    if status not in _icon_cache:
        _icon_cache[status] = create_tray_icon(status)
    return _icon_cache[status]
