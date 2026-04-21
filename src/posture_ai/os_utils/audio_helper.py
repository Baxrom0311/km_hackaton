import os
import sys
import subprocess
import threading
from pathlib import Path
from loguru import logger

from gtts import gTTS

# Audio fayllar config papkasida saqlanadi (CWD'ga bog'liq emas)
def _get_audio_dir() -> Path:
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

# ═══ Audio backend ═══
# pygame.mixer ba'zan Python 3.14+ da ishlamaydi, shuning uchun
# macOS: afplay, Linux: aplay/paplay, Windows: pygame fallback

_audio_backend = "none"

def _detect_backend() -> str:
    """Eng mos audio backend'ni aniqlash."""
    # 1. pygame.mixer sinash
    try:
        import pygame
        pygame.mixer.init()
        logger.info("Audio backend: pygame.mixer")
        return "pygame"
    except Exception:
        pass

    # 2. macOS afplay
    if sys.platform == "darwin":
        try:
            subprocess.run(["which", "afplay"], capture_output=True, check=True)
            logger.info("Audio backend: afplay (macOS)")
            return "afplay"
        except Exception:
            pass

    # 3. Linux aplay/paplay
    if sys.platform == "linux":
        for cmd in ("paplay", "aplay"):
            try:
                subprocess.run(["which", cmd], capture_output=True, check=True)
                logger.info(f"Audio backend: {cmd} (Linux)")
                return cmd
            except Exception:
                continue

    logger.warning("Audio backend topilmadi — ovozli ogohlantirishlar o'chirildi.")
    return "none"

_is_playing = False

def _play_with_backend(filepath: Path) -> None:
    """Backend orqali audio faylni o'ynatish."""
    global _is_playing, _audio_backend

    if _audio_backend == "none":
        return

    if _is_playing:
        return

    _is_playing = True
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
        _is_playing = False


def prepare_voices():
    """Checks if audio files exist, otherwise downloads them via gTTS.
       This allows completely offline usage after the very first start."""
    global _audio_backend
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)

    _audio_backend = _detect_backend()

    for key, (filename, full_text) in ALERTS_DATA.items():
        filepath = AUDIO_DIR / filename
        if not filepath.exists():
            logger.info(f"Ovoz yuklanmoqda: {filename}...")
            try:
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
        filename = ALERTS_DATA[issue_key][0]
        filepath = AUDIO_DIR / filename

        if filepath.exists():
            threading.Thread(target=_play_with_backend, args=(filepath,), daemon=True).start()
