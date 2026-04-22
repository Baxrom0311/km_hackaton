"""Application and tray icon helpers."""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap


STATUS_COLORS = {
    "good": "#2ecc71",
    "bad": "#e74c3c",
    "idle": "#f39c12",
    "off": "#95a5a6",
}

COMMON_ICON_SIZES = (16, 20, 24, 32, 40, 48, 64, 128, 256)


def _asset_candidates(filename: str) -> list[Path]:
    relative_path = Path("assets") / filename
    candidates: list[Path] = []

    frozen_root = getattr(sys, "_MEIPASS", None)
    if frozen_root:
        candidates.append(Path(frozen_root) / relative_path)

    candidates.extend(
        [
            Path(sys.executable).resolve().parent / relative_path,
            Path.cwd() / relative_path,
            Path(__file__).resolve().parents[3] / relative_path,
            Path(sys.prefix) / "share" / "posture-ai" / relative_path,
            Path(sys.base_prefix) / "share" / "posture-ai" / relative_path,
        ]
    )
    return candidates


def resolve_icon_asset() -> Path | None:
    names = ("icon.ico", "icon.png") if sys.platform == "win32" else ("icon.png", "icon.ico")
    for name in names:
        for candidate in _asset_candidates(name):
            if candidate.exists():
                return candidate
    return None


def _fallback_pixmap(size: int, color: str = "#2563eb") -> QPixmap:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    pen_width = max(1, size // 16)
    painter.setPen(QPen(QColor("#ffffff"), pen_width))
    painter.setBrush(QColor(color))
    margin = max(1, pen_width)
    painter.drawEllipse(QRect(margin, margin, size - margin * 2, size - margin * 2))
    painter.end()
    return pixmap


_app_icon: QIcon | None = None
_tray_icon_cache: dict[str, QIcon] = {}


def get_app_icon() -> QIcon:
    global _app_icon
    if _app_icon is not None:
        return _app_icon

    icon_path = resolve_icon_asset()
    if icon_path is not None:
        icon = QIcon(str(icon_path))
        if not icon.isNull():
            _app_icon = icon
            return icon

    icon = QIcon()
    for size in COMMON_ICON_SIZES:
        icon.addPixmap(_fallback_pixmap(size))
    _app_icon = icon
    return icon


def _base_pixmap(size: int) -> QPixmap:
    pixmap = get_app_icon().pixmap(size, size)
    if pixmap.isNull():
        return _fallback_pixmap(size)
    return pixmap


def _tray_pixmap(status: str, size: int) -> QPixmap:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    base = _base_pixmap(size).scaled(
        size,
        size,
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )
    x = (size - base.width()) // 2
    y = (size - base.height()) // 2
    painter.drawPixmap(x, y, base)

    badge_color = STATUS_COLORS.get(status)
    if badge_color:
        badge_size = max(6, int(size * 0.38))
        margin = max(1, size // 14)
        border_width = max(1, size // 18)
        rect = QRect(size - badge_size - margin, size - badge_size - margin, badge_size, badge_size)
        painter.setPen(QPen(QColor("#ffffff"), border_width))
        painter.setBrush(QColor(badge_color))
        painter.drawEllipse(rect)

    painter.end()
    return pixmap


def create_tray_icon(status: str) -> QIcon:
    icon = QIcon()
    for size in COMMON_ICON_SIZES:
        icon.addPixmap(_tray_pixmap(status, size))

    if icon.isNull():
        color = STATUS_COLORS.get(status, STATUS_COLORS["off"])
        icon.addPixmap(_fallback_pixmap(64, color))
    return icon


def get_tray_icon(status: str) -> QIcon:
    if status not in _tray_icon_cache:
        _tray_icon_cache[status] = create_tray_icon(status)
    return _tray_icon_cache[status]
