import os
import shutil
import sys
import subprocess
import threading
from pathlib import Path
from posture_ai.core.logger import logger

from posture_ai.core.config import get_app_data_dir

# Audio fayllar config papkasida saqlanadi (CWD'ga bog'liq emas)
def _get_audio_dir() -> Path:
    return get_app_data_dir() / "audio"

AUDIO_DIR = _get_audio_dir()

# These are the exact phrases from detector.py mapped to filenames
ALERTS_DATA = {
    "Boshingizni ko'taring!": ("head_up.mp3", "Iltimos, boshingizni ko'taring, o'tirishingizni to'g'irlang!"),
    "Yelkalaringizni tekislang!": ("shoulder.mp3", "Yelkalaringizni tekis tuting, qiyshaymang!"),
    "Oldinga engashmang!": ("lean.mp3", "Oldinga engashmang, bu umurtqangizga xavfli!"),
    "Orqaga yotmang!": ("lean_back.mp3", "Orqaga yotib ketibsiz, to'g'ri o'tiring!"),
    "Bo'yningizni to'g'rilang!": ("neck_rot.mp3", "Bo'yningiz burilgan, kameraga to'g'ri qarang!"),
    "Boshingiz qiyshaygan!": ("head_tilt.mp3", "Boshingiz yon tomonga qiyshaygan, tekis tuting!"),
    "Yelkalaringizni oching!": ("slouch.mp3", "Yelkalaringiz oldinga bukilgan, ko'ksingizni oching va orqaga torting!"),
    "Yelkangizni bo'shashtiring!": ("shoulder_relax.mp3", "Yelkangiz ko'tarilgan, chuqur nafas oling va yelkalarni bo'shashtiring!"),
    "Ekranga yaqin!": ("close.mp3", "Ekranga juda yaqinsiz, ko'zingizni asrang!"),
    "Ekrandan juda uzoqsiz!": ("too_far.mp3", "Ekrandan juda uzoqda o'tiribsiz, biroz yaqinroq keling!"),
    "Ekranga juda yaqinsiz!": ("too_close.mp3", "Ekranga juda yaqinsiz, biroz uzoqroq o'tiring!"),
    "Tanaffus qiling!": ("break.mp3", "Juda uzoq o'tirib qoldingiz, o'rningizdan turib biroz harakatlaning!"),
    "20-20-20!": ("rule20.mp3", "20-20-20 qoidasi! 20 metr uzoqlikka 20 soniya qarab ko'zlarni dam oldiring!"),
    "Charchoq belgilari: tanaffus qiling!": ("fatigue.mp3", "Charchoq belgilari ko'rinyapti, 2-5 daqiqa tanaffus qiling, turing va yelkangizni yozing!"),
}

# ═══ Audio backend ═══
# pygame.mixer ba'zan Python 3.14+ da ishlamaydi, shuning uchun
# macOS: afplay, Linux: aplay/paplay, Windows: pygame fallback

_audio_backend = "none"

def _detect_backend() -> str:
    """Eng mos audio backend'ni aniqlash."""
    # 1. macOS afplay — pygame/cv2 SDL duplicate warninglarini chetlab o'tadi
    if sys.platform == "darwin":
        if shutil.which("afplay"):
            logger.info("Audio backend: afplay (macOS)")
            return "afplay"

    # 2. pygame.mixer sinash
    try:
        import pygame
        pygame.mixer.init()
        logger.info("Audio backend: pygame.mixer")
        return "pygame"
    except Exception:
        pass

    # 3. Linux aplay/paplay
    if sys.platform == "linux":
        for cmd in ("paplay", "aplay"):
            if shutil.which(cmd):
                logger.info(f"Audio backend: {cmd} (Linux)")
                return cmd

    logger.warning("Audio backend topilmadi — ovozli ogohlantirishlar o'chirildi.")
    return "none"

_play_lock = threading.Lock()


def _speak_with_system_tts(text: str) -> bool:
    """Keshli audio bo'lmasa, OS'dagi lokal TTS backendini sinaydi."""
    try:
        if sys.platform == "darwin" and shutil.which("say"):
            subprocess.Popen(
                ["say", text],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return True

        if sys.platform == "linux":
            for cmd in ("spd-say", "espeak"):
                if shutil.which(cmd):
                    subprocess.Popen(
                        [cmd, text],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                    return True

        if sys.platform == "win32" and shutil.which("powershell"):
            escaped_text = text.replace("'", "''")
            script = (
                "Add-Type -AssemblyName System.Speech;"
                "$speak = New-Object System.Speech.Synthesis.SpeechSynthesizer;"
                f"$speak.Speak('{escaped_text}');"
            )
            subprocess.Popen(
                ["powershell", "-NoProfile", "-Command", script],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return True
    except Exception as e:
        logger.error(f"System TTS ishlatishda xatolik: {e}")
    return False

def _play_with_backend(filepath: Path) -> None:
    """Backend orqali audio faylni o'ynatish."""
    global _audio_backend

    if _audio_backend == "none":
        return

    if not _play_lock.acquire(blocking=False):
        return  # Boshqa audio hali o'ynayapti

    try:
        if _audio_backend == "pygame":
            import pygame
            if pygame.mixer.music.get_busy():
                return
            pygame.mixer.music.load(str(filepath))
            pygame.mixer.music.play()
        elif _audio_backend == "afplay":
            subprocess.Popen(
                ["afplay", str(filepath)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        elif _audio_backend in ("paplay", "aplay"):
            subprocess.Popen(
                [_audio_backend, str(filepath)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
    except Exception as e:
        logger.error(f"Ovozni o'ynatish xatosi: {e}")
    finally:
        _play_lock.release()


def prepare_voices():
    """TTS fayllarni tayyorlaydi.

    Monitoring lokal ishlaydi. Ovozli alertlar esa keshlangan mp3,
    OS'dagi lokal TTS yoki zarur bo'lsa gTTS cache orqali ishlaydi.
    """
    global _audio_backend
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)

    _audio_backend = _detect_backend()

    for key, (filename, full_text) in ALERTS_DATA.items():
        filepath = AUDIO_DIR / filename
        if not filepath.exists():
            logger.info(f"Ovoz yuklanmoqda: {filename}...")
            try:
                from gtts import gTTS

                # gTTS 'uz' tilini qo'llab-quvvatlamaydi, 'tr' (turk) eng yaqin alternativ
                for lang in ('uz', 'tr', 'en'):
                    try:
                        tts = gTTS(text=full_text, lang=lang, slow=False)
                        tts.save(str(filepath))
                        logger.info(f"Ovoz saqlandi ({lang}): {filename}")
                        break
                    except ValueError:
                        continue
            except Exception as e:
                logger.error(f"gTTS yuklashda xatolik: {e}")


def play_alert_for_issue(issue_key: str):
    """Plays the cached TTS alert for the given issue without freezing the app."""
    if issue_key in ALERTS_DATA:
        filename, full_text = ALERTS_DATA[issue_key]
        filepath = AUDIO_DIR / filename

        if filepath.exists():
            threading.Thread(target=_play_with_backend, args=(filepath,), daemon=True).start()
            return

        # Cache bo'lmasa ham lokal OS TTS bilan ovoz berishga urinamiz.
        threading.Thread(target=_speak_with_system_tts, args=(full_text,), daemon=True).start()
