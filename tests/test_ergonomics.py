from __future__ import annotations

import unittest
from dataclasses import dataclass

from posture_ai.core.ergonomics import (
    EyeGazeTracker,
    FatigueAlertTracker,
    SitDurationTracker,
    compute_ergonomic_score,
    compute_fatigue_score,
    estimate_face_camera_distance,
    fatigue_advice,
    fatigue_level,
    eye_strain_risk,
    is_facing_camera,
    sit_duration_risk,
)


@dataclass
class FakeLandmark:
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    visibility: float = 1.0


class FakeClock:
    def __init__(self, start: float = 0.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


class SitDurationTrackerTests(unittest.TestCase):
    def test_continuous_sit_accumulates_while_present(self) -> None:
        clock = FakeClock()
        tracker = SitDurationTracker(time_fn=clock)

        tracker.observe(person_present=True)
        clock.advance(120)
        tracker.observe(person_present=True)

        self.assertAlmostEqual(tracker.continuous_sit_seconds, 120.0, delta=0.01)

    def test_break_resets_after_threshold(self) -> None:
        clock = FakeClock()
        tracker = SitDurationTracker(break_threshold_sec=60, time_fn=clock)

        tracker.observe(person_present=True)
        clock.advance(300)
        tracker.observe(person_present=True)
        # User stands up
        clock.advance(120)
        tracker.observe(person_present=False)
        # User returns
        clock.advance(10)
        tracker.observe(person_present=True)

        self.assertLess(tracker.continuous_sit_seconds, 60.0)

    def test_short_absence_does_not_reset(self) -> None:
        clock = FakeClock()
        tracker = SitDurationTracker(break_threshold_sec=60, time_fn=clock)

        tracker.observe(person_present=True)
        clock.advance(600)
        tracker.observe(person_present=True)
        clock.advance(30)  # short glance away
        tracker.observe(person_present=False)
        clock.advance(5)
        tracker.observe(person_present=True)

        self.assertGreater(tracker.continuous_sit_seconds, 600.0)

    def test_alert_fires_after_threshold(self) -> None:
        clock = FakeClock()
        tracker = SitDurationTracker(
            alert_threshold_sec=60,
            cooldown_sec=10,
            time_fn=clock,
        )

        tracker.observe(person_present=True)
        clock.advance(30)
        tracker.observe(person_present=True)
        self.assertFalse(tracker.needs_break_alert())

        clock.advance(40)
        tracker.observe(person_present=True)
        self.assertTrue(tracker.needs_break_alert())
        # Cooldown blocks immediate re-alert
        self.assertFalse(tracker.needs_break_alert())


class EyeStrainTests(unittest.TestCase):
    def test_estimate_face_camera_distance(self) -> None:
        landmarks = [FakeLandmark() for _ in range(33)]
        landmarks[7] = FakeLandmark(x=0.40)
        landmarks[8] = FakeLandmark(x=0.65)

        self.assertAlmostEqual(estimate_face_camera_distance(landmarks), 0.25, places=2)

    def test_eye_strain_risk_zero_when_far(self) -> None:
        self.assertEqual(eye_strain_risk(0.10), 0.0)

    def test_eye_strain_risk_max_when_close(self) -> None:
        self.assertEqual(eye_strain_risk(0.40), 1.0)

    def test_eye_strain_risk_linear_in_band(self) -> None:
        risk = eye_strain_risk(0.25, safe_max=0.18, danger_min=0.32)
        self.assertGreater(risk, 0.0)
        self.assertLess(risk, 1.0)


class SitDurationRiskTests(unittest.TestCase):
    def test_no_risk_when_short_sit(self) -> None:
        self.assertEqual(sit_duration_risk(10 * 60), 0.0)

    def test_max_risk_when_very_long(self) -> None:
        self.assertEqual(sit_duration_risk(120 * 60), 1.0)


class EyeGazeTrackerTests(unittest.TestCase):
    def test_gaze_accumulates_while_facing(self) -> None:
        clock = FakeClock()
        tracker = EyeGazeTracker(time_fn=clock)

        tracker.observe(facing_screen=True)
        clock.advance(600)
        tracker.observe(facing_screen=True)

        self.assertAlmostEqual(tracker.continuous_gaze_seconds, 600.0, delta=0.01)

    def test_looking_away_resets_after_break(self) -> None:
        clock = FakeClock()
        tracker = EyeGazeTracker(break_duration_seconds=20, time_fn=clock)

        tracker.observe(facing_screen=True)
        clock.advance(300)
        tracker.observe(facing_screen=True)
        # User looks away
        clock.advance(30)
        tracker.observe(facing_screen=False)
        clock.advance(5)
        tracker.observe(facing_screen=True)

        self.assertLess(tracker.continuous_gaze_seconds, 60.0)

    def test_alert_fires_after_threshold(self) -> None:
        clock = FakeClock()
        tracker = EyeGazeTracker(
            gaze_alert_seconds=60,
            cooldown_sec=10,
            time_fn=clock,
        )

        tracker.observe(facing_screen=True)
        clock.advance(30)
        self.assertFalse(tracker.needs_gaze_alert())

        clock.advance(40)
        tracker.observe(facing_screen=True)
        self.assertTrue(tracker.needs_gaze_alert())
        self.assertFalse(tracker.needs_gaze_alert())  # cooldown


class FacingCameraTests(unittest.TestCase):
    def test_facing_when_nose_centered(self) -> None:
        landmarks = [FakeLandmark() for _ in range(33)]
        landmarks[0] = FakeLandmark(x=0.50)
        landmarks[7] = FakeLandmark(x=0.42)
        landmarks[8] = FakeLandmark(x=0.58)

        self.assertTrue(is_facing_camera(landmarks))

    def test_not_facing_when_turned(self) -> None:
        landmarks = [FakeLandmark() for _ in range(33)]
        landmarks[0] = FakeLandmark(x=0.70)  # nose far right
        landmarks[7] = FakeLandmark(x=0.42)
        landmarks[8] = FakeLandmark(x=0.58)

        self.assertFalse(is_facing_camera(landmarks))


class ErgonomicScoreTests(unittest.TestCase):
    def test_score_equals_posture_when_no_other_risk(self) -> None:
        score = compute_ergonomic_score(
            posture_score=80,
            continuous_sit_seconds=0,
            face_distance=0.10,
        )
        self.assertEqual(score, 80)

    def test_long_sit_penalises_score(self) -> None:
        score = compute_ergonomic_score(
            posture_score=90,
            continuous_sit_seconds=120 * 60,  # 2 hours straight
            face_distance=0.10,
        )
        self.assertLess(score, 90)

    def test_close_face_penalises_score(self) -> None:
        score = compute_ergonomic_score(
            posture_score=90,
            continuous_sit_seconds=0,
            face_distance=0.40,
        )
        self.assertLess(score, 90)

    def test_score_clamped_to_zero(self) -> None:
        score = compute_ergonomic_score(
            posture_score=0,
            continuous_sit_seconds=120 * 60,
            face_distance=0.40,
        )
        self.assertEqual(score, 0)

    def test_long_gaze_penalises_score(self) -> None:
        score = compute_ergonomic_score(
            posture_score=90,
            continuous_sit_seconds=0,
            face_distance=0.10,
            continuous_gaze_seconds=60 * 60,  # 1 soat uzluksiz tikilish
        )
        self.assertLess(score, 90)


class FatigueTests(unittest.TestCase):
    def test_fatigue_score_low_for_short_healthy_session(self) -> None:
        score = compute_fatigue_score(
            posture_score=95,
            continuous_sit_seconds=5 * 60,
            continuous_gaze_seconds=5 * 60,
            face_distance=0.12,
        )

        self.assertLess(score, 20)
        self.assertEqual(fatigue_level(score), "low")

    def test_fatigue_score_high_for_long_poor_session(self) -> None:
        score = compute_fatigue_score(
            posture_score=45,
            continuous_sit_seconds=90 * 60,
            continuous_gaze_seconds=75 * 60,
            face_distance=0.38,
        )

        self.assertGreaterEqual(score, 65)
        self.assertEqual(fatigue_level(score), "high")

    def test_fatigue_advice_recommends_break_when_high(self) -> None:
        advice = fatigue_advice(
            fatigue_score=70,
            continuous_sit_seconds=60 * 60,
            continuous_gaze_seconds=30 * 60,
            face_distance=0.30,
        )

        self.assertIn("tanaffus", advice.lower())

    def test_fatigue_alert_tracker_respects_cooldown(self) -> None:
        clock = FakeClock()
        tracker = FatigueAlertTracker(threshold=65, cooldown_sec=60, time_fn=clock)

        self.assertFalse(tracker.needs_fatigue_alert(64))
        self.assertTrue(tracker.needs_fatigue_alert(65))
        self.assertFalse(tracker.needs_fatigue_alert(80))

        clock.advance(61)
        self.assertTrue(tracker.needs_fatigue_alert(80))


if __name__ == "__main__":
    unittest.main()
