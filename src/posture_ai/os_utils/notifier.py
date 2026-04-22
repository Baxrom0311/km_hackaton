from __future__ import annotations

import importlib.util

import platform
import subprocess
from typing import Sequence

from loguru import logger

ISSUE_MESSAGES = {
    "Boshingizni ko'taring!": "Boshingizni ko'taring! Oldinga engashib ketibsiz.",
    "Yelkalaringizni tekislang!": "Yelkalaringizni tekislang.",
    "Oldinga engashmang!": "Oldinga engashmang. Orqangizni rostlang.",
    "Orqaga yotmang!": "Orqaga yotib ketibsiz. To'g'ri o'tiring.",
    "Bo'yningizni to'g'rilang!": "Bo'yningiz burilgan. Kameraga to'g'ri qarang.",
    "Boshingiz qiyshaygan!": "Boshingiz yon tomonga qiyshaygan. Boshingizni tekis tuting.",
    "Yelkalaringizni oching!": "Yelkalaringiz oldinga bukilgan. Ko'ksingizni oching va orqaga torting.",
    "Yelkangizni bo'shashtiring!": "Yelkangiz ko'tarilgan. Nafas olib, yelkalarni bo'shashtiring.",
    "Ekrandan juda uzoqsiz!": "Ekrandan juda uzoqda o'tiribsiz. Kameraga yaqinroq keling.",
    "Ekranga juda yaqinsiz!": "Ekranga juda yaqin o'tiribsiz. Biroz uzoqroq o'tiring.",
    "Tanaffus qiling!": "Uzoq vaqt o'tirdingiz. 1-2 daqiqa turing va cho'zilib oling.",
    "Ekranga yaqin!": "Ekranga juda yaqin o'tiribsiz. Ko'zlaringizni dam oldiring.",
    "20-20-20!": "20 daqiqa uzluksiz ekranga qaradingiz. 20 soniya 6 metr uzoqqa qarang.",
    "Charchoq belgilari: tanaffus qiling!": "Charchoq belgilari ko'rinyapti. 2-5 daqiqa tanaffus qiling, turing va yelkangizni yozing.",
}


def build_message(issues: Sequence[str]) -> str:
    if not issues:
        return "O'tirish pozitsiyangizni to'g'rilang."
    return "\n".join(ISSUE_MESSAGES.get(issue, issue) for issue in issues[:3])


def _plyer_available() -> bool:
    return importlib.util.find_spec("plyer") is not None


def send_notification(title: str, message: str = "", issues: Sequence[str] | None = None) -> bool:
    issues = list(issues or [])
    body = message or build_message(issues)
    os_name = platform.system()

    try:
        if os_name == "Windows":
            if _plyer_available():
                from plyer import notification

                notification.notify(
                    title=title,
                    message=body,
                    app_name="PostureAI",
                    timeout=5,
                )
                return True

            if importlib.util.find_spec("win10toast") is not None:
                from win10toast import ToastNotifier

                toaster = ToastNotifier()
                toaster.show_toast(title, body, duration=5, threaded=True)
                return True

        if os_name == "Darwin":
            safe_body = body.replace('"', '\\"')
            safe_title = title.replace('"', '\\"')
            subprocess.run(
                [
                    "osascript",
                    "-e",
                    f'display notification "{safe_body}" with title "{safe_title}"',
                ],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return True

        if os_name == "Linux":
            subprocess.run(
                ["notify-send", title, body],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return True
    except Exception:
        logger.exception("Notification could not be delivered")

    logger.warning("%s: %s", title, body)
    return False
