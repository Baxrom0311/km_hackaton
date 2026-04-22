from __future__ import annotations

import unittest

from posture_ai.core.forecast import (
    forecast_risk,
    _compute_r_squared,
    _compute_mape,
    _compute_confidence_interval,
    _linear_trend,
    _holt_predict,
    _wma_predict,
    _ensemble_predict,
)


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
        assert forecast is not None
        self.assertLess(forecast.current_risk, 50.0)

    # ═══ Yangi metrikalar testlari ═══

    def test_r_squared_in_forecast(self) -> None:
        forecast = forecast_risk(_week([80.0, 82.0, 79.0, 81.0, 83.0]))
        assert forecast is not None
        self.assertGreaterEqual(forecast.r_squared, 0.0)
        self.assertLessEqual(forecast.r_squared, 1.0)

    def test_mape_in_forecast(self) -> None:
        forecast = forecast_risk(_week([80.0, 82.0, 79.0, 81.0, 83.0]))
        assert forecast is not None
        self.assertGreaterEqual(forecast.mape, 0.0)

    def test_confidence_interval_in_forecast(self) -> None:
        forecast = forecast_risk(_week([60.0, 55.0, 50.0, 45.0, 40.0]))
        assert forecast is not None
        self.assertLessEqual(forecast.confidence_lower, forecast.projected_risk_7d)
        self.assertGreaterEqual(forecast.confidence_upper, forecast.projected_risk_7d)
        self.assertGreaterEqual(forecast.confidence_lower, 0.0)
        self.assertLessEqual(forecast.confidence_upper, 100.0)

    def test_perfect_r_squared_for_linear_data(self) -> None:
        # Mukammal chiziqli data → R² ≈ 1.0
        actual = [10.0, 20.0, 30.0, 40.0, 50.0]
        predicted = [10.0, 20.0, 30.0, 40.0, 50.0]
        r2 = _compute_r_squared(actual, predicted)
        self.assertAlmostEqual(r2, 1.0, places=5)

    def test_r_squared_zero_for_mean_prediction(self) -> None:
        actual = [10.0, 20.0, 30.0, 40.0, 50.0]
        mean_val = sum(actual) / len(actual)
        predicted = [mean_val] * len(actual)
        r2 = _compute_r_squared(actual, predicted)
        self.assertAlmostEqual(r2, 0.0, places=5)

    def test_mape_zero_for_perfect_prediction(self) -> None:
        actual = [10.0, 20.0, 30.0]
        predicted = [10.0, 20.0, 30.0]
        mape = _compute_mape(actual, predicted)
        self.assertAlmostEqual(mape, 0.0, places=5)

    def test_mape_with_known_error(self) -> None:
        actual = [100.0, 100.0]
        predicted = [90.0, 110.0]
        mape = _compute_mape(actual, predicted)
        self.assertAlmostEqual(mape, 10.0, places=5)

    def test_confidence_interval_bounds(self) -> None:
        values = [30.0, 35.0, 40.0, 45.0, 50.0]
        lower, upper = _compute_confidence_interval(values, 60.0)
        self.assertLess(lower, 60.0)
        self.assertGreater(upper, 60.0)
        self.assertGreaterEqual(lower, 0.0)
        self.assertLessEqual(upper, 100.0)

    def test_two_day_data_returns_confidence(self) -> None:
        forecast = forecast_risk(_week([70.0, 60.0]))
        assert forecast is not None
        self.assertGreaterEqual(forecast.confidence_lower, 0.0)
        self.assertLessEqual(forecast.confidence_upper, 100.0)

    # ═══ Individual model testlari ═══

    def test_linear_trend_direction(self) -> None:
        _, slope = _linear_trend([10.0, 20.0, 30.0, 40.0])
        self.assertGreater(slope, 0)

    def test_holt_predict_increases_for_upward_trend(self) -> None:
        values = [10.0, 20.0, 30.0, 40.0, 50.0]
        pred = _holt_predict(values, 3)
        self.assertGreater(pred, values[-1])

    def test_wma_gives_more_weight_to_recent(self) -> None:
        # Oxirgi qiymat katta bo'lsa WMA yuqoriroq bo'ladi
        wma_high = _wma_predict([10.0, 20.0, 30.0, 40.0, 90.0], 0)
        wma_low = _wma_predict([90.0, 40.0, 30.0, 20.0, 10.0], 0)
        self.assertGreater(wma_high, wma_low)

    def test_ensemble_predict_bounded(self) -> None:
        values = [50.0, 55.0, 60.0]
        pred = _ensemble_predict(values, 7)
        # Juda katta bo'lmasligi kerak (7 kun uchun)
        self.assertGreater(pred, 0.0)
        self.assertLess(pred, 200.0)


if __name__ == "__main__":
    unittest.main()
