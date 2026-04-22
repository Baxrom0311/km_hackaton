"""Posture scoring va calibration profil qurilishi.

PostureMetrics dan raqamli ball hisoblash va kalibrovka baseline yaratish.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from datetime import datetime
from typing import Sequence

from posture_ai.vision.metrics import (
    LandmarkLike,
    check_camera_distance,
    estimate_camera_angle,
    get_camera_roll_xy_deg,
    get_camera_yaw_xz_deg,
    get_forward_lean,
    get_head_tilt_angle,
    get_lateral_head_tilt,
    get_neck_rotation,
    get_pitch_yz_deg,
    get_roll_xy_deg,
    get_shoulder_elevation,
    get_shoulder_roundness,
    get_shoulder_symmetry,
    get_yaw_xz_deg,
)


@dataclass(slots=True)
class PostureMetrics:
    head_angle: float
    shoulder_diff: float
    forward_lean: float
    camera_distance: str = "ok"
    roll_xy_deg: float = 0.0
    yaw_xz_deg: float = 0.0
    pitch_yz_deg: float = 0.0
    camera_roll_xy_deg: float = 0.0
    camera_yaw_xz_deg: float = 0.0
    camera_pitch_yz_deg: float = 0.0
    neck_rotation: float = 0.0
    lateral_head_tilt: float = 0.0
    shoulder_roundness: float = 0.0
    shoulder_elevation: float = 0.0
    spine_score: int = 100
    camera_angle: float = 0.0


@dataclass(slots=True)
class PostureResult:
    status: str
    head_angle: float | None = None
    shoulder_diff: float | None = None
    forward_lean: float | None = None
    posture_score: int | None = None
    issues: list[str] = field(default_factory=list)
    skipped: bool = False
    reason: str | None = None
    camera_distance: str = "ok"
    face_distance: float | None = None
    sit_seconds: float = 0.0
    ergonomic_score: int | None = None
    fatigue_score: int | None = None
    fatigue_level: str | None = None
    fatigue_advice: str | None = None
    fatigue_alert: bool = False
    break_alert: bool = False
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))
    facing_camera: bool | None = None
    roll_xy_deg: float | None = None
    yaw_xz_deg: float | None = None
    pitch_yz_deg: float | None = None
    camera_roll_xy_deg: float | None = None
    camera_yaw_xz_deg: float | None = None
    camera_pitch_yz_deg: float | None = None
    neck_rotation: float | None = None
    lateral_head_tilt: float | None = None
    shoulder_elevation: float | None = None
    spine_score: int | None = None
    posture_trend_risk: float | None = None
    movement_risk: float | None = None
    head_drop_risk: float | None = None
    posture_stability_risk: float | None = None
    fatigue_factors: dict[str, float] = field(default_factory=dict)
    camera_angle: float | None = None


def calculate_spine_score(metrics: PostureMetrics) -> int:
    """Bosh, yelka, engashish va slouch signallaridan umumiy umurtqa balli."""
    head_risk = min(max(metrics.head_angle / 35.0, 0.0), 1.0)
    pitch_risk = min(max(abs(metrics.pitch_yz_deg) / 35.0, 0.0), 1.0)
    shoulder_risk = min(max(metrics.shoulder_diff / 0.12, 0.0), 1.0)
    slouch_risk = min(max(metrics.shoulder_roundness, 0.0), 1.0)
    elevation_risk = min(max(metrics.shoulder_elevation, 0.0), 1.0)

    penalty = (
        (head_risk * 24.0)
        + (pitch_risk * 24.0)
        + (shoulder_risk * 16.0)
        + (slouch_risk * 26.0)
        + (elevation_risk * 10.0)
    )
    return max(0, min(100, round(100.0 - penalty)))


def measure_posture_metrics(landmarks: Sequence[LandmarkLike]) -> PostureMetrics:
    camera_roll = get_camera_roll_xy_deg(landmarks)
    camera_yaw = get_camera_yaw_xz_deg(landmarks)
    camera_pitch = estimate_camera_angle(landmarks)
    roll = get_roll_xy_deg(landmarks)
    yaw = get_yaw_xz_deg(landmarks)
    pitch = get_pitch_yz_deg(landmarks)
    shoulder_roundness = get_shoulder_roundness(landmarks)
    shoulder_elevation = get_shoulder_elevation(landmarks)
    metrics = PostureMetrics(
        head_angle=get_head_tilt_angle(landmarks),
        shoulder_diff=get_shoulder_symmetry(landmarks),
        forward_lean=get_forward_lean(landmarks),
        camera_distance=check_camera_distance(landmarks),
        roll_xy_deg=roll,
        yaw_xz_deg=yaw,
        pitch_yz_deg=pitch,
        camera_roll_xy_deg=camera_roll,
        camera_yaw_xz_deg=camera_yaw,
        camera_pitch_yz_deg=camera_pitch,
        neck_rotation=min(abs(yaw) / 20.0, 1.0),
        lateral_head_tilt=abs(roll),
        shoulder_roundness=shoulder_roundness,
        shoulder_elevation=shoulder_elevation,
        camera_angle=camera_pitch,
    )
    metrics.spine_score = calculate_spine_score(metrics)
    return metrics


def _upper_metric_risk(value: float, baseline: float, threshold: float) -> float:
    baseline = min(baseline, threshold * 0.9)
    span = max(threshold - baseline, threshold * 0.2, 1e-6)
    if value <= baseline:
        return 0.0
    return min((value - baseline) / span, 1.0)


def _lower_metric_risk(value: float, baseline: float, threshold: float) -> float:
    baseline = max(baseline, threshold + abs(threshold) * 0.15)
    span = max(baseline - threshold, abs(threshold) * 0.2, 1e-6)
    if value >= baseline:
        return 0.0
    return min((baseline - value) / span, 1.0)


def calculate_posture_score(
    metrics: PostureMetrics,
    *,
    head_angle_threshold: float,
    shoulder_diff_threshold: float,
    forward_lean_threshold: float,
    roll_xy_threshold_deg: float = 12.0,
    yaw_xz_threshold_deg: float = 18.0,
    pitch_yz_threshold_deg: float = 18.0,
    baseline_head_angle: float | None = None,
    baseline_shoulder_diff: float | None = None,
    baseline_forward_lean: float | None = None,
    baseline_roll_xy_deg: float | None = None,
    baseline_yaw_xz_deg: float | None = None,
    baseline_pitch_yz_deg: float | None = None,
) -> int:
    head_baseline = (
        min(float(baseline_head_angle), head_angle_threshold * 0.9)
        if baseline_head_angle is not None
        else min(10.0, head_angle_threshold * 0.4)
    )
    shoulder_baseline = (
        min(float(baseline_shoulder_diff), shoulder_diff_threshold * 0.9)
        if baseline_shoulder_diff is not None
        else shoulder_diff_threshold * 0.25
    )
    forward_baseline = (
        max(float(baseline_forward_lean), forward_lean_threshold + 0.03)
        if baseline_forward_lean is not None
        else max(-0.05, forward_lean_threshold + 0.12)
    )
    roll_baseline = min(abs(float(baseline_roll_xy_deg or 0.0)), roll_xy_threshold_deg * 0.5)
    yaw_baseline = min(abs(float(baseline_yaw_xz_deg or 0.0)), yaw_xz_threshold_deg * 0.5)
    pitch_baseline = min(abs(float(baseline_pitch_yz_deg or 0.0)), pitch_yz_threshold_deg * 0.5)

    risk_head = _upper_metric_risk(metrics.head_angle, head_baseline, head_angle_threshold)
    risk_shoulder = _upper_metric_risk(metrics.shoulder_diff, shoulder_baseline, shoulder_diff_threshold)
    risk_forward = _lower_metric_risk(metrics.forward_lean, forward_baseline, forward_lean_threshold)
    risk_roll = _upper_metric_risk(abs(metrics.roll_xy_deg), roll_baseline, roll_xy_threshold_deg)
    risk_yaw = _upper_metric_risk(abs(metrics.yaw_xz_deg), yaw_baseline, yaw_xz_threshold_deg)
    risk_pitch = _upper_metric_risk(abs(metrics.pitch_yz_deg), pitch_baseline, pitch_yz_threshold_deg)

    risk_slouch = metrics.shoulder_roundness
    risk_shoulder_elevation = metrics.shoulder_elevation
    penalty = (
        (risk_head * 15.0)
        + (risk_shoulder * 10.0)
        + (risk_forward * 10.0)
        + (risk_pitch * 20.0)
        + (risk_yaw * 15.0)
        + (risk_roll * 10.0)
        + (risk_slouch * 15.0)
        + (risk_shoulder_elevation * 5.0)
    )
    return max(0, min(100, round(100.0 - penalty)))


def build_calibration_profile(samples: Sequence[PostureMetrics]) -> dict[str, float | int | str]:
    if not samples:
        raise ValueError("Calibration samples are required")

    head_baseline = statistics.median(sample.head_angle for sample in samples)
    shoulder_baseline = statistics.median(sample.shoulder_diff for sample in samples)
    forward_baseline = statistics.median(sample.forward_lean for sample in samples)
    roll_baseline = statistics.median(abs(sample.roll_xy_deg) for sample in samples)
    yaw_baseline = statistics.median(abs(sample.yaw_xz_deg) for sample in samples)
    pitch_baseline = statistics.median(abs(sample.pitch_yz_deg) for sample in samples)

    head_threshold = min(max(head_baseline + 8.0, 18.0), 35.0)
    shoulder_threshold = min(max(shoulder_baseline + 0.02, 0.03), 0.12)
    forward_threshold = max(min(forward_baseline - 0.12, -0.08), -0.40)
    roll_threshold = min(max(roll_baseline + 6.0, 8.0), 24.0)
    yaw_threshold = min(max(yaw_baseline + 8.0, 10.0), 30.0)
    pitch_threshold = min(max(pitch_baseline + 8.0, 10.0), 30.0)

    return {
        "baseline_head_angle": round(head_baseline, 2),
        "baseline_shoulder_diff": round(shoulder_baseline, 4),
        "baseline_forward_lean": round(forward_baseline, 4),
        "baseline_roll_xy_deg": round(roll_baseline, 2),
        "baseline_yaw_xz_deg": round(yaw_baseline, 2),
        "baseline_pitch_yz_deg": round(pitch_baseline, 2),
        "head_angle_threshold": round(head_threshold, 1),
        "shoulder_diff_threshold": round(shoulder_threshold, 4),
        "forward_lean_threshold": round(forward_threshold, 4),
        "roll_xy_threshold_deg": round(roll_threshold, 1),
        "yaw_xz_threshold_deg": round(yaw_threshold, 1),
        "pitch_yz_threshold_deg": round(pitch_threshold, 1),
        "calibration_samples": len(samples),
        "calibration_completed_at": datetime.now().isoformat(timespec="seconds"),
    }
