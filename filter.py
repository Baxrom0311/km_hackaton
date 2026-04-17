from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field
from typing import Callable


@dataclass(slots=True)
class TemporalFilter:
    window_size: int = 90
    threshold: float = 0.70
    cooldown_sec: float = 60.0
    time_fn: Callable[[], float] = time.time
    window: deque[int] = field(init=False)
    last_alert_time: float = field(default=float("-inf"), init=False)

    def __post_init__(self) -> None:
        if self.window_size <= 0:
            raise ValueError("window_size must be positive")
        if not 0 < self.threshold <= 1:
            raise ValueError("threshold must be between 0 and 1")
        if self.cooldown_sec < 0:
            raise ValueError("cooldown_sec must be >= 0")
        self.window = deque(maxlen=self.window_size)

    @property
    def bad_ratio(self) -> float:
        if not self.window:
            return 0.0
        return sum(self.window) / len(self.window)

    def update(self, is_bad: bool) -> bool:
        self.window.append(1 if is_bad else 0)

        if len(self.window) < self.window.maxlen:
            return False

        now = self.time_fn()
        cooldown_passed = (now - self.last_alert_time) >= self.cooldown_sec
        if self.bad_ratio >= self.threshold and cooldown_passed:
            self.last_alert_time = now
            self.window.clear()
            return True
        return False
