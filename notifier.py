from __future__ import annotations

import importlib.util
import logging
import platform
import subprocess
from typing import Sequence

logger = logging.getLogger(__name__)

ISSUE_MESSAGES = {
    "Boshingizni ko'taring!": "Boshingizni ko'taring! Oldinga engashib ketibsiz.",
    "Yelkalaringizni tekislang!": "Yelkalaringizni tekislang.",
    "Oldinga engashmang!": "Oldinga engashmang. Orqangizni rostlang.",
    "Tanaffus qiling!": "Uzoq vaqt o'tirdingiz. 1-2 daqiqa turing va cho'zilib oling.",
    "Ekranga yaqin!": "Ekranga juda yaqin o'tiribsiz. Ko'zlaringizni dam oldiring.",
    "20-20-20!": "20 daqiqa uzluksiz ekranga qaradingiz. 20 soniya 6 metr uzoqqa qarang.",
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
        if os_name == "Windows" and _plyer_available():
            from plyer import notification

            notification.notify(
                title=title,
                message=body,
                app_name="PostureAI",
                timeout=5,
            )
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
