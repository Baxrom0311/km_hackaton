from __future__ import annotations

import unittest
from dataclasses import dataclass

from detector import analyze_posture, build_calibration_profile, measure_posture_metrics


@dataclass
class FakeLandmark:
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    visibility: float = 1.0


def build_landmarks() -> list[FakeLandmark]:
    landmarks = [FakeLandmark() for _ in range(33)]

    landmarks[0] = FakeLandmark(x=0.525, y=0.20, z=-0.05)
    landmarks[7] = FakeLandmark(x=0.525, y=0.25, z=0.0)
    landmarks[8] = FakeLandmark(x=0.525, y=0.25, z=0.0)
    landmarks[11] = FakeLandmark(x=0.40, y=0.50, z=0.0)
    landmarks[12] = FakeLandmark(x=0.65, y=0.50, z=0.0)
    landmarks[23] = FakeLandmark(x=0.42, y=0.80, z=0.0)
    landmarks[24] = FakeLandmark(x=0.63, y=0.80, z=0.0)
    return landmarks


class DetectorTests(unittest.TestCase):
    def test_analyze_posture_detects_good_alignment(self) -> None:
        result = analyze_posture(build_landmarks())

        self.assertEqual(result.status, "good")
        self.assertFalse(result.skipped)
        self.assertEqual(result.issues, [])
        self.assertLessEqual(result.head_angle or 0.0, 25.0)
        self.assertGreaterEqual(result.posture_score or 0, 80)

    def test_analyze_posture_flags_multiple_issues(self) -> None:
        landmarks = build_landmarks()
        landmarks[0] = FakeLandmark(x=0.74, y=0.22, z=-0.45)
        landmarks[7] = FakeLandmark(x=0.75, y=0.35, z=0.0)
        landmarks[8] = FakeLandmark(x=0.75, y=0.35, z=0.0)
        landmarks[11] = FakeLandmark(x=0.40, y=0.45, z=0.0)
        landmarks[12] = FakeLandmark(x=0.65, y=0.55, z=0.0)

        result = analyze_posture(landmarks)

        self.assertEqual(result.status, "bad")
        self.assertIn("Boshingizni ko'taring!", result.issues)
        self.assertIn("Yelkalaringizni tekislang!", result.issues)
        self.assertIn("Oldinga engashmang!", result.issues)
        self.assertIsNotNone(result.posture_score)
        self.assertLessEqual(result.posture_score, 25)

    def test_analyze_posture_skips_when_visibility_is_low(self) -> None:
        landmarks = build_landmarks()
        landmarks[11].visibility = 0.1

        result = analyze_posture(landmarks)

        self.assertTrue(result.skipped)
        self.assertEqual(result.reason, "low_visibility")

    def test_analyze_posture_allows_low_hip_visibility_for_desktop_view(self) -> None:
        landmarks = build_landmarks()
        landmarks[23].visibility = 0.1
        landmarks[24].visibility = 0.1

        result = analyze_posture(landmarks)

        self.assertFalse(result.skipped)
        self.assertEqual(result.status, "good")

    def test_build_calibration_profile_returns_personalized_thresholds(self) -> None:
        samples = [
            measure_posture_metrics(build_landmarks()),
            measure_posture_metrics(build_landmarks()),
            measure_posture_metrics(build_landmarks()),
        ]

        profile = build_calibration_profile(samples)

        self.assertGreater(profile["head_angle_threshold"], profile["baseline_head_angle"])
        self.assertGreater(profile["shoulder_diff_threshold"], profile["baseline_shoulder_diff"])
        self.assertLess(profile["forward_lean_threshold"], profile["baseline_forward_lean"])


if __name__ == "__main__":
    unittest.main()
