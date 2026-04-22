from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    from loguru import logger as logger
except ImportError:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )

    class _FallbackLogger:
        """Small Loguru-compatible wrapper used before dependencies are installed."""

        def __init__(self) -> None:
            self._logger = logging.getLogger("posture_ai")

        def add(self, sink: str | Path, *args: Any, level: str = "INFO", **kwargs: Any) -> int:
            try:
                path = Path(str(sink).replace("{time}", datetime.now().strftime("%Y%m%d_%H%M%S")))
                path.parent.mkdir(parents=True, exist_ok=True)
                handler = logging.FileHandler(path, encoding="utf-8")
                handler.setLevel(getattr(logging, str(level).upper(), logging.INFO))
                handler.setFormatter(
                    logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")
                )
                self._logger.addHandler(handler)
                return len(self._logger.handlers)
            except Exception:
                return 0

        def debug(self, message: str, *args: Any, **kwargs: Any) -> None:
            self._logger.debug(message, *args, **kwargs)

        def info(self, message: str, *args: Any, **kwargs: Any) -> None:
            self._logger.info(message, *args, **kwargs)

        def warning(self, message: str, *args: Any, **kwargs: Any) -> None:
            self._logger.warning(message, *args, **kwargs)

        def error(self, message: str, *args: Any, **kwargs: Any) -> None:
            self._logger.error(message, *args, **kwargs)

        def exception(self, message: str, *args: Any, **kwargs: Any) -> None:
            self._logger.exception(message, *args, **kwargs)

    logger = _FallbackLogger()
