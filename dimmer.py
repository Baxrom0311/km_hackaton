"""Ekranni xira qilish moduli — noto'g'ri posture uchun nudge.

macOS: CoreGraphics gamma API orqali ekranni xiraytiradi.
Linux: xrandr orqali brightness o'zgartiradi.
Windows: WMI/SetDeviceGammaRamp orqali (hozircha faqat fallback log).

Ishlash tartibi:
  1. Posture bad → dim_screen() chaqiriladi (brightness tushadi)
  2. Posture yaxshilansa yoki timeout o'tsa → restore_screen()
  3. Ilova yopilganda albatta restore_screen() chaqiriladi (finally)
"""

from __future__ import annotations

import logging
import platform
import subprocess
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

_SYSTEM = platform.system()


def _macos_set_brightness(level: float) -> bool:
    """macOS: CoreGraphics gamma API orqali brightness o'rnatadi.

    `level`: 0.0 (qop-qora) .. 1.0 (to'liq yorug'lik).
    """
    try:
        import Quartz

        (err, display_count, displays) = Quartz.CGGetActiveDisplayList(16, None, None)
        if err != 0 or not displays:
            return False
        for display_id in displays:
            Quartz.CGDisplaySetBrightness(display_id, level)
        return True
    except Exception:
        logger.debug("CGDisplaySetBrightness ishlamadi, gamma fallback sinab ko'rilmoqda")

    try:
        import Quartz

        (err, display_count, displays) = Quartz.CGGetActiveDisplayList(16, None, None)
        if err != 0 or not displays:
            return False
        for display_id in displays:
            Quartz.CGSetDisplayTransferByFormula(
                display_id,
                0.0, level, 1.0,  # red
                0.0, level, 1.0,  # green
                0.0, level, 1.0,  # blue
            )
        return True
    except Exception:
        logger.debug("macOS gamma fallback ham ishlamadi")
        return False


def _macos_restore() -> bool:
    try:
        import Quartz

        (err, display_count, displays) = Quartz.CGGetActiveDisplayList(16, None, None)
        if err != 0 or not displays:
            return False
        for display_id in displays:
            try:
                Quartz.CGDisplaySetBrightness(display_id, 1.0)
            except Exception:
                pass
            Quartz.CGDisplayRestoreColorSyncSettings()
        return True
    except Exception:
        return False


def _linux_set_brightness(level: float) -> bool:
    try:
        subprocess.run(
            ["xrandr", "--output", "eDP-1", "--brightness", str(level)],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return True
    except Exception:
        return False


def _linux_restore() -> bool:
    return _linux_set_brightness(1.0)


@dataclass(slots=True)
class ScreenDimmer:
    """Ekran xiraytirish boshqaruvchisi.

    dim_level: xiraytirish darajasi (0.3 = ancha xira, 0.7 = biroz xira)
    is_dimmed: hozir xira holatdami
    """

    dim_level: float = 0.4
    is_dimmed: bool = field(default=False, init=False)
    _original_level: float = field(default=1.0, init=False)

    def dim(self) -> bool:
        if self.is_dimmed:
            return True

        success = False
        if _SYSTEM == "Darwin":
            success = _macos_set_brightness(self.dim_level)
        elif _SYSTEM == "Linux":
            success = _linux_set_brightness(self.dim_level)
        else:
            logger.info("Screen dim: %s platformasi uchun hozircha qo'llab-quvvatlanmaydi", _SYSTEM)

        if success:
            self.is_dimmed = True
            logger.info("Ekran xiraytirildi (level=%.1f)", self.dim_level)
        return success

    def restore(self) -> bool:
        if not self.is_dimmed:
            return True

        success = False
        if _SYSTEM == "Darwin":
            success = _macos_restore()
        elif _SYSTEM == "Linux":
            success = _linux_restore()

        if success:
            self.is_dimmed = False
            logger.info("Ekran yorug'ligi tiklandi")
        return success

    def __del__(self) -> None:
        if self.is_dimmed:
            self.restore()
