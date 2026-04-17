from __future__ import annotations

import unittest

from filter import TemporalFilter


class FakeClock:
    def __init__(self, now: float = 100.0) -> None:
        self.now = now

    def time(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


class TemporalFilterTests(unittest.TestCase):
    def test_alert_triggers_after_window_reaches_threshold(self) -> None:
        clock = FakeClock()
        filter_ = TemporalFilter(window_size=3, threshold=0.67, cooldown_sec=10, time_fn=clock.time)

        self.assertFalse(filter_.update(True))
        self.assertFalse(filter_.update(True))
        self.assertTrue(filter_.update(True))

    def test_cooldown_blocks_repeated_alerts_until_elapsed(self) -> None:
        clock = FakeClock()
        filter_ = TemporalFilter(window_size=3, threshold=0.67, cooldown_sec=10, time_fn=clock.time)

        for _ in range(2):
            self.assertFalse(filter_.update(True))
        self.assertTrue(filter_.update(True))

        for _ in range(3):
            self.assertFalse(filter_.update(True))

        clock.advance(10)
        self.assertTrue(filter_.update(True))
        self.assertFalse(filter_.update(True))
        self.assertFalse(filter_.update(True))
        self.assertFalse(filter_.update(True))
        clock.advance(10)
        self.assertTrue(filter_.update(True))


if __name__ == "__main__":
    unittest.main()
