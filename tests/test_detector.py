from __future__ import annotations

import unittest
import math
from dataclasses import dataclass

from posture_ai.vision.detector import analyze_posture, build_calibration_profile, measure_posture_metrics


@dataclass
class FakeLandmark:
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    visibility: float = 1.0


def build_landmarks() -> list[FakeLandmark]:
    landmarks = [FakeLandmark() for _ in range(33)]

    landmarks[0] = FakeLandmark(x=0.525, y=0.20, z=-0.05)
    landmarks[7] = FakeLandmark(x=0.45, y=0.25, z=0.0)
    landmarks[8] = FakeLandmark(x=0.60, y=0.25, z=0.0)
    landmarks[11] = FakeLandmark(x=0.40, y=0.50, z=0.0)
    landmarks[12] = FakeLandmark(x=0.65, y=0.50, z=0.0)
    landmarks[23] = FakeLandmark(x=0.42, y=0.80, z=0.0)
    landmarks[24] = FakeLandmark(x=0.63, y=0.80, z=0.0)
    return landmarks


def apply_view_roll(landmarks: list[FakeLandmark], angle_deg: float) -> None:
    slope = math.tan(math.radians(angle_deg))
    center_x = 0.525
    original_y = {idx: landmarks[idx].y for idx in (7, 8, 11, 12)}
    for idx in (7, 8, 11, 12):
        landmarks[idx].y = original_y[idx] + (landmarks[idx].x - center_x) * slope


def apply_view_yaw(landmarks: list[FakeLandmark], angle_deg: float) -> None:
    slope = math.tan(math.radians(angle_deg))
    for left_idx, right_idx in ((7, 8), (11, 12)):
        left = landmarks[left_idx]
        right = landmarks[right_idx]
        center_x = (left.x + right.x) / 2.0
        for idx in (left_idx, right_idx):
            landmarks[idx].z = (landmarks[idx].x - center_x) * slope


class DetectorTests(unittest.TestCase):
    def test_analyze_posture_detects_good_alignment(self) -> None:
        result = analyze_posture(build_landmarks())

        self.assertEqual(result.status, "good")
        self.assertFalse(result.skipped)
        self.assertEqual(result.issues, [])
        self.assertLessEqual(result.head_angle or 0.0, 25.0)
        self.assertGreaterEqual(result.posture_score or 0, 80)
        self.assertIsNotNone(result.roll_xy_deg)
        self.assertIsNotNone(result.yaw_xz_deg)
        self.assertIsNotNone(result.pitch_yz_deg)
        self.assertIsNotNone(result.spine_score)
        self.assertGreaterEqual(result.spine_score or 0, 70)

    def test_analyze_posture_flags_multiple_issues(self) -> None:
        landmarks = build_landmarks()
        landmarks[0] = FakeLandmark(x=0.74, y=0.45, z=-0.45)
        landmarks[7] = FakeLandmark(x=0.65, y=0.35, z=0.0)
        landmarks[8] = FakeLandmark(x=0.85, y=0.35, z=0.0)
        landmarks[11] = FakeLandmark(x=0.40, y=0.45, z=0.0)
        landmarks[12] = FakeLandmark(x=0.65, y=0.53, z=0.0)

        result = analyze_posture(landmarks)

        self.assertEqual(result.status, "bad")
        self.assertIn("Boshingizni ko'taring!", result.issues)
        self.assertIn("Yelkalaringizni tekislang!", result.issues)
        self.assertIn("Oldinga engashmang!", result.issues)
        self.assertIsNotNone(result.posture_score)
        self.assertLessEqual(result.posture_score, 45)

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

    def test_analyze_posture_flags_3d_rotation_and_tilt(self) -> None:
        landmarks = build_landmarks()
        landmarks[7] = FakeLandmark(x=0.45, y=0.18, z=-0.18)
        landmarks[8] = FakeLandmark(x=0.60, y=0.32, z=0.18)
        landmarks[11] = FakeLandmark(x=0.40, y=0.50, z=0.0)
        landmarks[12] = FakeLandmark(x=0.65, y=0.50, z=0.0)

        result = analyze_posture(
            landmarks,
            roll_xy_threshold_deg=10.0,
            yaw_xz_threshold_deg=10.0,
        )

        self.assertEqual(result.status, "bad")
        self.assertIn("Bo'yningizni to'g'rilang!", result.issues)
        self.assertIn("Boshingiz qiyshaygan!", result.issues)

    def test_analyze_posture_flags_shoulder_elevation(self) -> None:
        landmarks = build_landmarks()
        landmarks[11].y = 0.31
        landmarks[12].y = 0.31

        result = analyze_posture(landmarks)

        self.assertEqual(result.status, "bad")
        self.assertIn("Yelkangizni bo'shashtiring!", result.issues)
        self.assertIsNotNone(result.shoulder_elevation)
        self.assertGreater(result.shoulder_elevation or 0.0, 0.75)

    def test_camera_roll_is_compensated_before_head_tilt_detection(self) -> None:
        landmarks = build_landmarks()
        apply_view_roll(landmarks, 18.0)

        result = analyze_posture(landmarks, roll_xy_threshold_deg=10.0)

        self.assertAlmostEqual(result.roll_xy_deg or 0.0, 0.0, delta=0.5)
        self.assertAlmostEqual(result.camera_roll_xy_deg or 0.0, 18.0, delta=0.5)
        self.assertNotIn("Boshingiz qiyshaygan!", result.issues)

    def test_side_camera_yaw_is_compensated_before_neck_rotation_detection(self) -> None:
        landmarks = build_landmarks()
        apply_view_yaw(landmarks, 45.0)

        result = analyze_posture(landmarks, yaw_xz_threshold_deg=10.0)

        self.assertAlmostEqual(result.yaw_xz_deg or 0.0, 0.0, delta=0.5)
        self.assertAlmostEqual(result.camera_yaw_xz_deg or 0.0, 45.0, delta=0.5)
        self.assertNotIn("Bo'yningizni to'g'rilang!", result.issues)
        self.assertNotIn("Kamerani yuzingizga yaqinroq to'g'rilang!", result.issues)

    def test_camera_distance_issues_are_not_duplicated(self) -> None:
        landmarks = build_landmarks()
        landmarks[11] = FakeLandmark(x=0.50, y=0.50, z=0.0)
        landmarks[12] = FakeLandmark(x=0.54, y=0.50, z=0.0)

        result = analyze_posture(landmarks)

        self.assertEqual(result.issues.count("Ekrandan juda uzoqsiz!"), 1)

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
        self.assertIn("baseline_roll_xy_deg", profile)
        self.assertIn("baseline_yaw_xz_deg", profile)
        self.assertIn("baseline_pitch_yz_deg", profile)


if __name__ == "__main__":
    unittest.main()
