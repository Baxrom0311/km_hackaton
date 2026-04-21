"""PostureAI — Dasturni ishga tushirish.

Ishga tushirish rejimlari:
  python main.py                → Dashboard oynasi ochiladi + tray icon
  python main.py --background   → Faqat tray icon (oyna yo'q, Tailscale kabi)
  python main.py --bg           → Xuddi --background

Dastur faqat 1 nusxada ishlaydi (singleton lock).
"""

import os
import sys

# SDL2 duplicate library warning'larni bostiramiz (cv2 + pygame konflikt)
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import argparse
import threading
from pathlib import Path
from loguru import logger
from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtCore import QSharedMemory

from posture_ai.core.config import load_config
from posture_ai.database.storage import Storage
from posture_ai.gui.main_window import DashboardWindow
from posture_ai.os_utils.audio_helper import prepare_voices


def configure_logging():
    log_dir = Path.home() / ".config" / "PostureAI" / "logs"
    if sys.platform == "win32":
        import os
        log_dir = Path(os.getenv("APPDATA", "~")).expanduser() / "PostureAI" / "logs"

    log_dir.mkdir(parents=True, exist_ok=True)

    logger.add(
        str(log_dir / "posture_ai_{time}.log"),
        rotation="5 MB",
        retention="10 days",
        level="INFO",
    )
    logger.info("Dastur ishga tushirildi.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="PostureAI — Ergonomik monitoring tizimi")
    parser.add_argument(
        "--background", "--bg",
        action="store_true",
        help="Orqa fon rejimi — faqat tray icon, oyna ko'rsatilmaydi",
    )
    return parser.parse_args()


def main():
    configure_logging()
    args = parse_args()

    # Ctrl+C bilan to'xtatish imkoniyati
    import signal
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    app = QApplication(sys.argv)
    app.setApplicationName("PostureAI")
    app.setQuitOnLastWindowClosed(False)  # Oyna yopilsa ham dastur ishlaydi

    # Singleton lock — faqat 1 nusxa
    shared_mem = QSharedMemory("PostureAI_Singleton_Lock")
    if not shared_mem.create(1):
        # Stale lock bo'lishi mumkin (pkill/crash dan keyin) — tozalashga urinish
        shared_mem.attach()
        shared_mem.detach()
        if not shared_mem.create(1):
            logger.warning("Dastur allaqachon ishga tushirilgan.")
            msg = QMessageBox()
            msg.setIcon(QMessageBox.Icon.Warning)
            msg.setWindowTitle("Diqqat")
            msg.setText("PostureAI allaqachon ishlamoqda.\nTray ikonkasini tekshiring.")
            msg.exec()
            sys.exit(0)

    # Config yuklash
    config = load_config()

    # Background rejim: --background flag yoki config.start_minimized
    start_minimized = args.background or config.start_minimized

    # Audio ovozlarini tayyorlash (asinxron)
    logger.info("Ovozli signallar tayyorlanmoqda...")
    threading.Thread(target=prepare_voices, daemon=True).start()

    # Database — config papkasida saqlanadi
    if sys.platform == "win32":
        import os
        db_dir = Path(os.getenv("APPDATA", "~")).expanduser() / "PostureAI"
    else:
        db_dir = Path.home() / ".config" / "PostureAI"
    db_dir.mkdir(parents=True, exist_ok=True)
    db_path = str(db_dir / "posture.db")
    storage = Storage(db_path)
    storage.initialize()
    logger.info("Database ulangan.")

    # Dashboard oyna + tray yaratish
    try:
        window = DashboardWindow(config, storage, start_minimized=start_minimized)

        if start_minimized:
            # Tailscale-style: faqat tray, oyna ko'rsatilmaydi
            logger.info("Background rejimda ishga tushdi. Tray ikonkasidan boshqaring.")
        else:
            window.show()
            logger.info("Dashboard oynasi ochildi.")

        sys.exit(app.exec())
    except Exception as e:
        logger.exception("Dastur xatosi:")


if __name__ == "__main__":
    main()
