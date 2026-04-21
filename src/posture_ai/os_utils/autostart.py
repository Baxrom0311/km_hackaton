"""Tizim ishga tushganda PostureAI'ni avtomatik yoqish/o'chirish.

macOS:  ~/Library/LaunchAgents/com.postureai.plist
Linux:  ~/.config/autostart/postureai.desktop
Windows: HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run
"""

import sys
import shutil
from pathlib import Path
from loguru import logger

APP_NAME = "PostureAI"


def _get_executable() -> str:
    """Hozirgi ishga tushirilgan dastur yo'lini aniqlash."""
    exe = shutil.which("posture-ai")
    if exe:
        return exe
    return f"{sys.executable} -m posture_ai.main"


# ═══ macOS ═══

_LAUNCH_AGENT_DIR = Path.home() / "Library" / "LaunchAgents"
_PLIST_PATH = _LAUNCH_AGENT_DIR / "com.postureai.plist"

_PLIST_TEMPLATE = """\
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.postureai</string>
    <key>ProgramArguments</key>
    <array>
        {program_args}
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <false/>
</dict>
</plist>
"""


def _macos_enable() -> bool:
    try:
        _LAUNCH_AGENT_DIR.mkdir(parents=True, exist_ok=True)
        exe = _get_executable()
        args = exe.split()
        args.append("--background")
        args_xml = "\n        ".join(f"<string>{a}</string>" for a in args)
        _PLIST_PATH.write_text(
            _PLIST_TEMPLATE.format(program_args=args_xml), encoding="utf-8"
        )
        logger.info(f"macOS autostart yoqildi: {_PLIST_PATH}")
        return True
    except Exception as e:
        logger.error(f"macOS autostart xatosi: {e}")
        return False


def _macos_disable() -> bool:
    try:
        if _PLIST_PATH.exists():
            _PLIST_PATH.unlink()
            logger.info("macOS autostart o'chirildi.")
        return True
    except Exception as e:
        logger.error(f"macOS autostart o'chirishda xato: {e}")
        return False


def _macos_is_enabled() -> bool:
    return _PLIST_PATH.exists()


# ═══ Linux ═══

_LINUX_AUTOSTART_DIR = Path.home() / ".config" / "autostart"
_DESKTOP_PATH = _LINUX_AUTOSTART_DIR / "postureai.desktop"

_DESKTOP_TEMPLATE = """\
[Desktop Entry]
Type=Application
Name=PostureAI
Exec={exe} --background
Hidden=false
NoDisplay=false
X-GNOME-Autostart-enabled=true
Comment=Ergonomik holat monitoring tizimi
"""


def _linux_enable() -> bool:
    try:
        _LINUX_AUTOSTART_DIR.mkdir(parents=True, exist_ok=True)
        exe = _get_executable()
        _DESKTOP_PATH.write_text(
            _DESKTOP_TEMPLATE.format(exe=exe), encoding="utf-8"
        )
        logger.info(f"Linux autostart yoqildi: {_DESKTOP_PATH}")
        return True
    except Exception as e:
        logger.error(f"Linux autostart xatosi: {e}")
        return False


def _linux_disable() -> bool:
    try:
        if _DESKTOP_PATH.exists():
            _DESKTOP_PATH.unlink()
            logger.info("Linux autostart o'chirildi.")
        return True
    except Exception as e:
        logger.error(f"Linux autostart o'chirishda xato: {e}")
        return False


def _linux_is_enabled() -> bool:
    return _DESKTOP_PATH.exists()


# ═══ Windows ═══

_WIN_REG_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
_WIN_REG_NAME = "PostureAI"


def _windows_enable() -> bool:
    try:
        import winreg
        exe = _get_executable()
        cmd = f'"{exe}" --background' if " " not in exe else f"{exe} --background"
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, _WIN_REG_KEY, 0, winreg.KEY_SET_VALUE)
        winreg.SetValueEx(key, _WIN_REG_NAME, 0, winreg.REG_SZ, cmd)
        winreg.CloseKey(key)
        logger.info("Windows autostart yoqildi (Registry).")
        return True
    except Exception as e:
        logger.error(f"Windows autostart xatosi: {e}")
        return False


def _windows_disable() -> bool:
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, _WIN_REG_KEY, 0, winreg.KEY_SET_VALUE)
        try:
            winreg.DeleteValue(key, _WIN_REG_NAME)
        except FileNotFoundError:
            pass
        winreg.CloseKey(key)
        logger.info("Windows autostart o'chirildi.")
        return True
    except Exception as e:
        logger.error(f"Windows autostart o'chirishda xato: {e}")
        return False


def _windows_is_enabled() -> bool:
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, _WIN_REG_KEY, 0, winreg.KEY_READ)
        try:
            winreg.QueryValueEx(key, _WIN_REG_NAME)
            winreg.CloseKey(key)
            return True
        except FileNotFoundError:
            winreg.CloseKey(key)
            return False
    except Exception:
        return False


# ═══ Public API ═══

def enable_autostart() -> bool:
    if sys.platform == "darwin":
        return _macos_enable()
    elif sys.platform == "win32":
        return _windows_enable()
    elif sys.platform == "linux":
        return _linux_enable()
    logger.warning(f"Autostart: {sys.platform} qo'llab-quvvatlanmaydi.")
    return False


def disable_autostart() -> bool:
    if sys.platform == "darwin":
        return _macos_disable()
    elif sys.platform == "win32":
        return _windows_disable()
    elif sys.platform == "linux":
        return _linux_disable()
    return False


def is_autostart_enabled() -> bool:
    if sys.platform == "darwin":
        return _macos_is_enabled()
    elif sys.platform == "win32":
        return _windows_is_enabled()
    elif sys.platform == "linux":
        return _linux_is_enabled()
    return False
