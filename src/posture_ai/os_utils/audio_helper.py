import os
import threading
from pathlib import Path
from loguru import logger

# Pygame mixer for fast playback without blocking GUI
import pygame

# gTTS for downloading high quality TTS files
from gtts import gTTS

# Audio fayllar config papkasida saqlanadi (CWD'ga bog'liq emas)
def _get_audio_dir() -> Path:
    import sys, os
    if sys.platform == "win32":
        base = Path(os.getenv("APPDATA", "~")).expanduser() / "PostureAI"
    else:
        base = Path.home() / ".config" / "PostureAI"
    return base / "audio"

AUDIO_DIR = _get_audio_dir()

# These are the exact phrases from detector.py mapped to filenames
ALERTS_DATA = {
    "Boshingizni ko'taring!": ("head_up.mp3", "Iltimos, boshingizni ko'taring, o'tirishingizni to'g'irlang!"),
    "Yelkalaringizni tekislang!": ("shoulder.mp3", "Yelkalaringizni tekis tuting, qiyshaymang!"),
    "Oldinga engashmang!": ("lean.mp3", "Oldinga engashmang, bu umurtqangizga xavfli!"),
    "Ekranga yaqin!": ("close.mp3", "Ekranga juda yaqinsiz, ko'zingizni asrang!"),
    "Tanaffus qiling!": ("break.mp3", "Juda uzoq o'tirib qoldingiz, o'rningizdan turib biroz harakatlaning!"),
    "20-20-20!": ("rule20.mp3", "20-20-20 qoidasi! 20 metr uzoqlikka 20 soniya qarab ko'zlarni dam oldiring!"),
}

_is_mixer_initialized = False

def init_audio():
    """Initializes pygame mixer safely if not already done."""
    global _is_mixer_initialized
    if not _is_mixer_initialized:
        try:
            pygame.mixer.init()
            _is_mixer_initialized = True
            logger.info("Audio tizimi (PyGame) ishga tushdi.")
        except Exception as e:
            logger.error(f"PyGame mixer xatoligi: {e}")

def prepare_voices():
    """Checks if audio files exist, otherwise downloads them via gTTS. 
       This allows completely offline usage after the very first start."""
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    
    for key, (filename, full_text) in ALERTS_DATA.items():
        filepath = AUDIO_DIR / filename
        if not filepath.exists():
            logger.info(f"Ovoz yuklanmoqda: {filename}...")
            try:
                tts = gTTS(text=full_text, lang='uz', slow=False)
                tts.save(str(filepath))
            except Exception as e:
                logger.error(f"gTTS yuklashda xatolik: {e}")

def _play_audio_thread(filepath: Path):
    init_audio()
    if not _is_mixer_initialized: return
    
    try:
        # Avoid interrupting already playing alert
        if pygame.mixer.music.get_busy():
            return
            
        pygame.mixer.music.load(str(filepath))
        pygame.mixer.music.play()
    except Exception as e:
        logger.error(f"Ovozni o'ynatish xatosi: {e}")

def play_alert_for_issue(issue_key: str):
    """Plays the cached TTS alert for the given issue without freezing the app."""
    if issue_key in ALERTS_DATA:
        filename = ALERTS_DATA[issue_key][0]
        filepath = AUDIO_DIR / filename
        
        if filepath.exists():
            # Start in short living thread just in case load is blocking
            threading.Thread(target=_play_audio_thread, args=(filepath,), daemon=True).start()
