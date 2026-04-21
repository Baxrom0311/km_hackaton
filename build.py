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

    command = [
        sys.executable, "-m", "PyInstaller",
        "--name=PostureAI",
        "--windowed",                 # Terminal ochiq qolmasligi uchun (GUI ilova)
        "--onedir",                   # Papka shaklida saqlash (oson ishga tushadi)
        "--add-data=models/pose_landmarker_heavy.task:models",  # MediaPipe modelini qadoqlash
        "--hidden-import=posture_ai",
        "--hidden-import=posture_ai.core",
        "--hidden-import=posture_ai.vision",
        "--hidden-import=posture_ai.gui",
        "--hidden-import=posture_ai.gui.pages",
        "--hidden-import=posture_ai.os_utils",
        "--hidden-import=posture_ai.database",
        "src/posture_ai/main.py"      # Asosiy ishga tushiruvchi fayl
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
