import sys
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
        level="INFO"
    )
    logger.info("Dastur ishga tushirildi.")

def main():
    configure_logging()
    
    app = QApplication(sys.argv)
    app.setApplicationName("PostureAI")
    
    # Dasturni faqat 1 nusxada ishlatish (Singleton Lock)
    shared_mem = QSharedMemory("PostureAI_Singleton_Lock")
    if not shared_mem.create(1):
        logger.warning("Dastur allaqachon orqa fonda ishga tushirilgan. Kopiya yopilmoqda...")
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Icon.Warning)
        msg.setWindowTitle("Diqqat")
        msg.setText("PostureAI tizimi allaqachon ishlamoqda (Burchakdagi menyuni tekshiring).")
        msg.exec()
        sys.exit(0)
    
    # Load config (from pydantic)
    config = load_config()

    # Audio Oflayn Ovozlarini tekshirish va yuklash (Asinxron - bloklamaydi)
    logger.info("Ovozli signallar tayyorlanmoqda (Background)...")
    threading.Thread(target=prepare_voices, daemon=True).start()

    # Init database
    db_path = "posture.db"
    storage = Storage(db_path)
    storage.initialize()
    logger.info("Database ulangan.")

    # Show dashboard
    try:
        window = DashboardWindow(config, storage)
        window.show()
        logger.info("Dashboard oynasi ochildi.")
        
        sys.exit(app.exec())
    except Exception as e:
        logger.exception("Dastur xatosi:")
        
if __name__ == "__main__":
    main()
