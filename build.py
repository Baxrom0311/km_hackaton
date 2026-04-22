import os
import sys
import subprocess

def build():
    print("PostureAI: Dasturni executable (*.exe, *.app) ko'rinishida yig'ish boshlandi...")

    try:
        import PyInstaller
    except ImportError:
        print("PyInstaller topilmadi. O'rnatilmoqda...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])

    # Separator: macOS/Linux = ':', Windows = ';'
    sep = ";" if sys.platform == "win32" else ":"

    command = [
        sys.executable, "-m", "PyInstaller",
        "--name=PostureAI",
        "--windowed",
        "--onedir",
        f"--add-data=models/pose_landmarker_heavy.task{sep}models",
        # ── Barcha paket modullari ──
        "--hidden-import=posture_ai",
        "--hidden-import=posture_ai.core",
        "--hidden-import=posture_ai.core.config",
        "--hidden-import=posture_ai.core.filter",
        "--hidden-import=posture_ai.core.ergonomics",
        "--hidden-import=posture_ai.vision",
        "--hidden-import=posture_ai.vision.metrics",
        "--hidden-import=posture_ai.vision.scoring",
        "--hidden-import=posture_ai.vision.detector",
        "--hidden-import=posture_ai.vision.camera_worker",
        "--hidden-import=posture_ai.gui",
        "--hidden-import=posture_ai.gui.pages",
        "--hidden-import=posture_ai.gui.pages.dashboard",
        "--hidden-import=posture_ai.gui.pages.calibration",
        "--hidden-import=posture_ai.gui.pages.settings",
        "--hidden-import=posture_ai.gui.main_window",
        "--hidden-import=posture_ai.gui.styles",
        "--hidden-import=posture_ai.gui.tray_icons",
        "--hidden-import=posture_ai.os_utils",
        "--hidden-import=posture_ai.os_utils.notifier",
        "--hidden-import=posture_ai.os_utils.dimmer",
        "--hidden-import=posture_ai.os_utils.audio_helper",
        "--hidden-import=posture_ai.os_utils.autostart",
        "--hidden-import=posture_ai.database",
        "--hidden-import=posture_ai.database.storage",
        # ── Tashqi kutubxonalar ──
        "--hidden-import=mediapipe",
        "--hidden-import=cv2",
        "--hidden-import=pydantic",
        "--hidden-import=loguru",
        "--hidden-import=gtts",
        "--hidden-import=numpy",
        "--hidden-import=statistics",
        # ── Ixtiyoriy (mavjud bo'lsa import) ──
        "--hidden-import=pygame",
        "--hidden-import=pygame.mixer",
        "--collect-submodules=mediapipe",
        "src/posture_ai/main.py",
    ]

    # Platforma-specific ikonka (mavjud bo'lsa)
    if sys.platform == "darwin":
        for icon_path in ("assets/icon.icns", "assets/icon.png"):
            if os.path.exists(icon_path):
                command.append(f"--icon={icon_path}")
                break
    elif sys.platform == "win32":
        icon_path = "assets/icon.ico"
        if os.path.exists(icon_path):
            command.append(f"--icon={icon_path}")

    print(f"Ishga tushirilmoqda: {' '.join(command)}")
    result = subprocess.run(command)

    if result.returncode == 0:
        print("Qadoqlash muvaffaqiyatli yakunlandi! Natija 'dist/PostureAI' papkasida joylashgan.")
    else:
        print("Qadoqlashda xatolik yuz berdi.")

if __name__ == "__main__":
    build()
