from __future__ import annotations

import unittest

from posture_ai.core.forecast import forecast_risk


def _week(scores: list[float]) -> list[dict]:
    return [
        {"day": f"2026-04-{10 + i:02d}", "avg_ergonomic": score, "avg_score": score}
        for i, score in enumerate(scores)
    ]


class ForecastTests(unittest.TestCase):
    def test_returns_none_when_empty(self) -> None:
        self.assertIsNone(forecast_risk([]))

    def test_returns_none_with_single_day(self) -> None:
        self.assertIsNone(forecast_risk(_week([80.0])))

    def test_low_risk_for_consistently_good_scores(self) -> None:
        forecast = forecast_risk(_week([90.0, 92.0, 91.0, 93.0, 90.0]))
        assert forecast is not None
        self.assertEqual(forecast.category, "low")
        self.assertLess(forecast.current_risk, 25.0)

    def test_high_risk_for_consistently_bad_scores(self) -> None:
        forecast = forecast_risk(_week([40.0, 35.0, 38.0, 30.0, 32.0]))
        assert forecast is not None
        self.assertIn(forecast.category, {"high", "critical"})
        self.assertGreater(forecast.current_risk, 50.0)

    def test_negative_slope_when_improving(self) -> None:
        # risk yiqilib bormoqda (score o'sib bormoqda)
        forecast = forecast_risk(_week([50.0, 60.0, 70.0, 80.0, 90.0]))
        assert forecast is not None
        self.assertLess(forecast.slope_per_day, 0)

    def test_positive_slope_when_worsening(self) -> None:
        forecast = forecast_risk(_week([90.0, 80.0, 70.0, 60.0, 50.0]))
        assert forecast is not None
        self.assertGreater(forecast.slope_per_day, 0)

    def test_pain_probability_in_range(self) -> None:
        forecast = forecast_risk(_week([60.0, 55.0, 50.0, 45.0]))
        assert forecast is not None
        self.assertGreaterEqual(forecast.pain_probability_30d, 0.0)
        self.assertLessEqual(forecast.pain_probability_30d, 1.0)

    def test_falls_back_to_avg_score_when_ergonomic_missing(self) -> None:
        weekly = [
            {"day": "2026-04-10", "avg_ergonomic": 0.0, "avg_score": 80.0},
            {"day": "2026-04-11", "avg_ergonomic": 0.0, "avg_score": 75.0},
        ]
        forecast = forecast_risk(weekly)
        self.assertIsNotNone(forecast)


if __name__ == "__main__":
    unittest.main()
