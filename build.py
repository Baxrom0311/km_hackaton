import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def build():
    print("PostureAI: Dasturni executable (*.exe, *.app) ko'rinishida yig'ish boshlandi...")

    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        print("PyInstaller topilmadi. O'rnatilmoqda...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])

    # Separator: macOS/Linux = ':', Windows = ';'
    sep = ";" if sys.platform == "win32" else ":"
    entrypoint = ROOT / "src" / "posture_ai" / "main.py"

    heavy_optional_modules = [
        # MediaPipe ships optional GenAI/benchmark/test modules that can pull
        # CUDA PyTorch and scientific stacks into the bundle.
        "torch",
        "torchvision",
        "torchaudio",
        "transformers",
        "tokenizers",
        "jax",
        "jaxlib",
        "sentencepiece",
        "sklearn",
        "scipy",
        "IPython",
        "jedi",
        "nbformat",
        "zmq",
        "tornado",
    ]

    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--name=PostureAI",
        "--windowed",
        "--onedir",
        "--noconfirm",
        "--clean",
        f"--add-data=models/pose_landmarker_heavy.task{sep}models",
        f"--add-data=assets/icon.png{sep}assets",
        f"--add-data=assets/icon.ico{sep}assets",
        f"--add-data=assets/icon.icns{sep}assets",
        # App modules.
        "--hidden-import=posture_ai",
        "--hidden-import=posture_ai.core",
        "--hidden-import=posture_ai.core.config",
        "--hidden-import=posture_ai.core.filter",
        "--hidden-import=posture_ai.core.ergonomics",
        "--hidden-import=posture_ai.core.exercises",
        "--hidden-import=posture_ai.core.forecast",
        "--hidden-import=posture_ai.core.logger",
        "--hidden-import=posture_ai.core.session",
        "--hidden-import=posture_ai.vision",
        "--hidden-import=posture_ai.vision.metrics",
        "--hidden-import=posture_ai.vision.scoring",
        "--hidden-import=posture_ai.vision.detector",
        "--hidden-import=posture_ai.vision.camera_worker",
        "--hidden-import=posture_ai.gui",
        "--hidden-import=posture_ai.gui.pages",
        "--hidden-import=posture_ai.gui.pages.camera",
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
        # Third-party runtime modules.
        "--hidden-import=mediapipe",
        "--hidden-import=mediapipe.tasks.python.vision.pose_landmarker",
        "--hidden-import=mediapipe.tasks.python.vision.core.vision_task_running_mode",
        "--hidden-import=cv2",
        "--hidden-import=pydantic",
        "--hidden-import=loguru",
        "--hidden-import=gtts",
        "--hidden-import=numpy",
        "--hidden-import=statistics",
        "--hidden-import=plyer",
        "--hidden-import=plyer.platforms.win.notification",
        # Optional audio package used when installed.
        "--hidden-import=pygame",
        "--hidden-import=pygame.mixer",
        "--collect-data=mediapipe",
        "--collect-binaries=mediapipe",
        str(entrypoint),
    ]

    for module_name in heavy_optional_modules:
        command.append(f"--exclude-module={module_name}")

    # Platform-specific icon.
    if sys.platform == "darwin":
        for icon_path in ("assets/icon.icns", "assets/icon.png"):
            if (ROOT / icon_path).exists():
                command.append(f"--icon={icon_path}")
                break
    elif sys.platform == "win32":
        icon_path = "assets/icon.ico"
        if (ROOT / icon_path).exists():
            command.append(f"--icon={icon_path}")

    print(f"Ishga tushirilmoqda: {' '.join(command)}")
    result = subprocess.run(command)

    if result.returncode == 0:
        print("Qadoqlash muvaffaqiyatli yakunlandi! Natija 'dist/PostureAI' papkasida joylashgan.")
    else:
        print("Qadoqlashda xatolik yuz berdi.")
    raise SystemExit(result.returncode)


if __name__ == "__main__":
    build()
