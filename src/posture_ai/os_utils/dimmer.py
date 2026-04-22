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

import ctypes

import platform
import subprocess
from dataclasses import dataclass, field
from typing import Any

from loguru import logger

_SYSTEM = platform.system()

# Windows GDI32 gamma ramp strukturasi
_GDI_RAMP_SIZE = 256


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


def _linux_get_connected_outputs() -> list[str]:
    """xrandr orqali ulangan monitorlar nomlarini olish."""
    try:
        result = subprocess.run(
            ["xrandr", "--query"],
            capture_output=True, text=True, check=True,
        )
        outputs = []
        for line in result.stdout.splitlines():
            if " connected" in line:
                outputs.append(line.split()[0])
        return outputs
    except Exception:
        return []


def _linux_set_brightness(level: float) -> bool:
    outputs = _linux_get_connected_outputs()
    if not outputs:
        return False
    success = False
    for output in outputs:
        try:
            subprocess.run(
                ["xrandr", "--output", output, "--brightness", str(level)],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            success = True
        except Exception:
            logger.debug("xrandr brightness %s uchun ishlamadi: %s", output, level)
    return success


def _linux_restore() -> bool:
    return _linux_set_brightness(1.0)


def _windows_set_brightness(level: float) -> bool:
    """Windows: SetDeviceGammaRamp orqali ekranni xiraytiradi."""
    try:
        gdi32 = ctypes.windll.gdi32  # type: ignore[attr-defined]
        user32 = ctypes.windll.user32  # type: ignore[attr-defined]
        hdc = user32.GetDC(0)
        if not hdc:
            return False

        ramp = (ctypes.c_ushort * _GDI_RAMP_SIZE * 3)()
        for i in range(_GDI_RAMP_SIZE):
            val = min(65535, int(i * 256 * level))
            ramp[0][i] = val  # Red
            ramp[1][i] = val  # Green
            ramp[2][i] = val  # Blue

        result = gdi32.SetDeviceGammaRamp(hdc, ctypes.byref(ramp))
        user32.ReleaseDC(0, hdc)
        return bool(result)
    except Exception:
        logger.debug("Windows SetDeviceGammaRamp ishlamadi")
        return False


def _windows_restore() -> bool:
    """Windows: Gamma ramp'ni standart qiymatga tiklaydi."""
    try:
        gdi32 = ctypes.windll.gdi32  # type: ignore[attr-defined]
        user32 = ctypes.windll.user32  # type: ignore[attr-defined]
        hdc = user32.GetDC(0)
        if not hdc:
            return False

        ramp = (ctypes.c_ushort * _GDI_RAMP_SIZE * 3)()
        for i in range(_GDI_RAMP_SIZE):
            val = i * 256
            ramp[0][i] = val
            ramp[1][i] = val
            ramp[2][i] = val

        result = gdi32.SetDeviceGammaRamp(hdc, ctypes.byref(ramp))
        user32.ReleaseDC(0, hdc)
        return bool(result)
    except Exception:
        return False


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
        elif _SYSTEM == "Windows":
            success = _windows_set_brightness(self.dim_level)
        elif _SYSTEM == "Linux":
            success = _linux_set_brightness(self.dim_level)
        else:
            logger.info("Screen dim: %s platformasi uchun qo'llab-quvvatlanmaydi", _SYSTEM)

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
        elif _SYSTEM == "Windows":
            success = _windows_restore()
        elif _SYSTEM == "Linux":
            success = _linux_restore()

        if success:
            self.is_dimmed = False
            logger.info("Ekran yorug'ligi tiklandi")
        return success

    def __del__(self) -> None:
        if self.is_dimmed:
            self.restore()
