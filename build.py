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
        "--add-data=models/pose_landmarker_heavy.task:models", # MediaPipe modelini qadoqlash
        "src/posture_ai/main.py"      # Asosiy ishga tushiruvchi fayl
    ]

    if sys.platform == "darwin":
        command.append("--icon=assets/icon_good.png") 
    elif sys.platform == "win32":
        command.append("--icon=assets/icon_good.ico")

    print(f"Ishga tushirilmoqda: {' '.join(command)}")
    result = subprocess.run(command)

    if result.returncode == 0:
        print("✅ Qadoqlash muvaffaqiyatli yakunlandi! Natija 'dist/PostureAI' papkasida joylashgan.")
    else:
        print("❌ Qadoqlashda xatolik yuz berdi.")

if __name__ == "__main__":
    build()
