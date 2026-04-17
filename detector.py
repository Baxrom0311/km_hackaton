from __future__ import annotations

import importlib.util
import logging
import math
import statistics
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from queue import Queue
from typing import Any, Protocol, Sequence

from ergonomics import (
    EyeGazeTracker,
    SitDurationTracker,
    compute_ergonomic_score,
    estimate_face_camera_distance,
    eye_strain_risk,
    is_facing_camera,
)
from filter import TemporalFilter

logger = logging.getLogger(__name__)

# Upper-body webcam posture uchun burun, quloqlar va yelkalar yetarli.
# Son landmarklarini majburiy qilish desktop view'da keragidan ortiq skip beradi.
REQUIRED_LANDMARKS = (0, 7, 8, 11, 12)


class LandmarkLike(Protocol):
    x: float
    y: float
    z: float
    visibility: float


@dataclass(slots=True)
class PostureMetrics:
    head_angle: float
    shoulder_diff: float
    forward_lean: float
    camera_distance: str = "ok"


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
    break_alert: bool = False
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))


class DependencyUnavailableError(RuntimeError):
    pass


def check_runtime_dependencies() -> list[str]:
    missing: list[str] = []
    for module_name in ("cv2", "mediapipe"):
        if importlib.util.find_spec(module_name) is None:
            missing.append(module_name)
    return missing


def calculate_angle(a: tuple[float, float], b: tuple[float, float], c: tuple[float, float]) -> float:
    ab = (a[0] - b[0], a[1] - b[1])
    cb = (c[0] - b[0], c[1] - b[1])
    ab_norm = math.hypot(*ab)
    cb_norm = math.hypot(*cb)
    if ab_norm == 0 or cb_norm == 0:
        return 0.0
    cosine = ((ab[0] * cb[0]) + (ab[1] * cb[1])) / (ab_norm * cb_norm)
    cosine = max(-1.0, min(1.0, cosine))
    return math.degrees(math.acos(cosine))


def _average_point(landmarks: Sequence[LandmarkLike], indexes: Sequence[int]) -> tuple[float, float]:
    total_x = 0.0
    total_y = 0.0
    for index in indexes:
        total_x += landmarks[index].x
        total_y += landmarks[index].y
    count = float(len(indexes))
    return total_x / count, total_y / count


def required_landmarks_visible(landmarks: Sequence[LandmarkLike], min_visibility: float = 0.7) -> bool:
    try:
        return all(landmarks[index].visibility >= min_visibility for index in REQUIRED_LANDMARKS)
    except IndexError:
        return False


def get_head_tilt_angle(landmarks: Sequence[LandmarkLike]) -> float:
    ear = _average_point(landmarks, (7, 8))
    shoulder = _average_point(landmarks, (11, 12))
    vertical = (shoulder[0], shoulder[1] - 0.1)
    return calculate_angle(ear, shoulder, vertical)


def get_shoulder_symmetry(landmarks: Sequence[LandmarkLike]) -> float:
    left_y = landmarks[11].y
    right_y = landmarks[12].y
    return abs(left_y - right_y)


def get_forward_lean(landmarks: Sequence[LandmarkLike]) -> float:
    nose_z = landmarks[0].z
    shoulder_z = (landmarks[11].z + landmarks[12].z) / 2
    return nose_z - shoulder_z


def check_camera_distance(landmarks: Sequence[LandmarkLike]) -> str:
    distance = abs(landmarks[11].x - landmarks[12].x)
    if distance < 0.15:
        return "too_far"
    if distance > 0.50:
        return "too_close"
    return "ok"


def measure_posture_metrics(landmarks: Sequence[LandmarkLike]) -> PostureMetrics:
    return PostureMetrics(
        head_angle=get_head_tilt_angle(landmarks),
        shoulder_diff=get_shoulder_symmetry(landmarks),
        forward_lean=get_forward_lean(landmarks),
        camera_distance=check_camera_distance(landmarks),
    )


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
    baseline_head_angle: float | None = None,
    baseline_shoulder_diff: float | None = None,
    baseline_forward_lean: float | None = None,
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

    risk_head = _upper_metric_risk(metrics.head_angle, head_baseline, head_angle_threshold)
    risk_shoulder = _upper_metric_risk(metrics.shoulder_diff, shoulder_baseline, shoulder_diff_threshold)
    risk_forward = _lower_metric_risk(metrics.forward_lean, forward_baseline, forward_lean_threshold)

    penalty = (risk_head * 40.0) + (risk_shoulder * 20.0) + (risk_forward * 40.0)
    return max(0, min(100, round(100.0 - penalty)))


def build_calibration_profile(samples: Sequence[PostureMetrics]) -> dict[str, float | int | str]:
    if not samples:
        raise ValueError("Calibration samples are required")

    head_baseline = statistics.median(sample.head_angle for sample in samples)
    shoulder_baseline = statistics.median(sample.shoulder_diff for sample in samples)
    forward_baseline = statistics.median(sample.forward_lean for sample in samples)

    head_threshold = min(max(head_baseline + 8.0, 18.0), 35.0)
    shoulder_threshold = min(max(shoulder_baseline + 0.02, 0.03), 0.12)
    forward_threshold = max(min(forward_baseline - 0.12, -0.08), -0.40)

    return {
        "baseline_head_angle": round(head_baseline, 2),
        "baseline_shoulder_diff": round(shoulder_baseline, 4),
        "baseline_forward_lean": round(forward_baseline, 4),
        "head_angle_threshold": round(head_threshold, 1),
        "shoulder_diff_threshold": round(shoulder_threshold, 4),
        "forward_lean_threshold": round(forward_threshold, 4),
        "calibration_samples": len(samples),
        "calibration_completed_at": datetime.now().isoformat(timespec="seconds"),
    }


def analyze_posture(
    landmarks: Sequence[LandmarkLike],
    *,
    head_angle_threshold: float = 25.0,
    shoulder_diff_threshold: float = 0.07,
    forward_lean_threshold: float = -0.2,
    min_visibility: float = 0.7,
    baseline_head_angle: float | None = None,
    baseline_shoulder_diff: float | None = None,
    baseline_forward_lean: float | None = None,
) -> PostureResult:
    if not required_landmarks_visible(landmarks, min_visibility=min_visibility):
        return PostureResult(status="unknown", skipped=True, reason="low_visibility")

    metrics = measure_posture_metrics(landmarks)
    if metrics.camera_distance != "ok":
        return PostureResult(
            status="unknown",
            skipped=True,
            reason=metrics.camera_distance,
            camera_distance=metrics.camera_distance,
        )

    issues: list[str] = []
    if metrics.head_angle > head_angle_threshold:
        issues.append("Boshingizni ko'taring!")
    if metrics.shoulder_diff > shoulder_diff_threshold:
        issues.append("Yelkalaringizni tekislang!")
    if metrics.forward_lean < forward_lean_threshold:
        issues.append("Oldinga engashmang!")

    face_distance = estimate_face_camera_distance(landmarks)
    if eye_strain_risk(face_distance) >= 0.75:
        issues.append("Ekranga yaqin!")

    posture_score = calculate_posture_score(
        metrics,
        head_angle_threshold=head_angle_threshold,
        shoulder_diff_threshold=shoulder_diff_threshold,
        forward_lean_threshold=forward_lean_threshold,
        baseline_head_angle=baseline_head_angle,
        baseline_shoulder_diff=baseline_shoulder_diff,
        baseline_forward_lean=baseline_forward_lean,
    )

    return PostureResult(
        status="bad" if issues else "good",
        head_angle=round(metrics.head_angle, 1),
        shoulder_diff=round(metrics.shoulder_diff, 4),
        forward_lean=round(metrics.forward_lean, 4),
        posture_score=posture_score,
        issues=issues,
        camera_distance=metrics.camera_distance,
        face_distance=round(face_distance, 4),
    )


class PoseDetector:
    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config
        try:
            import cv2
            import mediapipe as mp
        except ImportError as exc:
            raise DependencyUnavailableError(
                "cv2 va mediapipe o'rnatilmagan. `pip install -r requirements.txt` ni ishga tushiring."
            ) from exc

        self.cv2 = cv2
        self.mp = mp
        self.capture = None
        self.pose = None
        self.backend = "tasks" if hasattr(mp, "tasks") and hasattr(mp.tasks, "vision") else "solutions"

    def open(self) -> None:
        if self.capture is not None:
            return

        self.capture = self.cv2.VideoCapture(int(self.config["camera_index"]))
        if hasattr(self.cv2, "CAP_PROP_BUFFERSIZE"):
            self.capture.set(self.cv2.CAP_PROP_BUFFERSIZE, 1)
        if not self.capture.isOpened():
            self.capture.release()
            self.capture = None
            raise RuntimeError("Kamerani ochib bo'lmadi. `camera_index` ni tekshiring.")

        if self.backend == "tasks":
            model_path = Path(str(self.config.get("model_asset_path", "models/pose_landmarker_heavy.task"))).expanduser()
            if not model_path.exists():
                raise RuntimeError(
                    f"Pose model fayli topilmadi: {model_path}. "
                    "Rasmiy `pose_landmarker_*.task` modelini shu yo'lga joylang."
                )

            base_options = self.mp.tasks.BaseOptions(model_asset_path=str(model_path))
            options = self.mp.tasks.vision.PoseLandmarkerOptions(
                base_options=base_options,
                running_mode=self.mp.tasks.vision.RunningMode.VIDEO,
                num_poses=1,
                min_pose_detection_confidence=float(self.config.get("min_detection_confidence", 0.5)),
                min_pose_presence_confidence=float(self.config.get("min_pose_presence_confidence", 0.5)),
                min_tracking_confidence=float(self.config.get("min_tracking_confidence", 0.5)),
                output_segmentation_masks=False,
            )
            self.pose = self.mp.tasks.vision.PoseLandmarker.create_from_options(options)
            return

        self.pose = self.mp.solutions.pose.Pose(
            model_complexity=int(self.config.get("model_complexity", 2)),
            enable_segmentation=False,
            min_detection_confidence=float(self.config.get("min_detection_confidence", 0.5)),
            min_tracking_confidence=float(self.config.get("min_tracking_confidence", 0.5)),
        )

    def close(self) -> None:
        if self.pose is not None:
            self.pose.close()
            self.pose = None
        if self.capture is not None:
            self.capture.release()
            self.capture = None

    def read(self) -> tuple[bool, Any]:
        if self.capture is None:
            raise RuntimeError("Camera is not open")
        return self.capture.read()

    def extract_landmarks(self, frame: Any) -> Sequence[LandmarkLike] | None:
        if self.pose is None:
            raise RuntimeError("Pose model is not initialized")

        rgb_frame = self.cv2.cvtColor(frame, self.cv2.COLOR_BGR2RGB)
        if self.backend == "tasks":
            mp_image = self.mp.Image(image_format=self.mp.ImageFormat.SRGB, data=rgb_frame)
            timestamp_ms = time.monotonic_ns() // 1_000_000
            pose_result = self.pose.detect_for_video(mp_image, timestamp_ms)
            if not pose_result.pose_landmarks:
                return None
            return pose_result.pose_landmarks[0]

        pose_result = self.pose.process(rgb_frame)
        if not pose_result.pose_landmarks:
            return None
        return pose_result.pose_landmarks.landmark

    def process_frame(self, frame: Any) -> PostureResult:
        landmarks = self.extract_landmarks(frame)
        if landmarks is None:
            return PostureResult(status="unknown", skipped=True, reason="no_pose")

        return analyze_posture(
            landmarks,
            head_angle_threshold=float(self.config["head_angle_threshold"]),
            shoulder_diff_threshold=float(self.config["shoulder_diff_threshold"]),
            forward_lean_threshold=float(self.config["forward_lean_threshold"]),
            min_visibility=float(self.config.get("min_visibility", 0.7)),
            baseline_head_angle=self.config.get("baseline_head_angle"),
            baseline_shoulder_diff=self.config.get("baseline_shoulder_diff"),
            baseline_forward_lean=self.config.get("baseline_forward_lean"),
        )


def collect_calibration_profile(
    config: dict[str, Any],
    *,
    duration_sec: float | None = None,
    min_samples: int | None = None,
) -> dict[str, float | int | str]:
    fps = max(int(config.get("fps", 10)), 1)
    frame_interval = 1.0 / fps
    target_duration = float(duration_sec or config.get("calibration_seconds", 12))
    required_samples = int(min_samples or config.get("calibration_min_samples", 25))
    min_visibility = float(config.get("min_visibility", 0.7))

    detector = PoseDetector(config)
    samples: list[PostureMetrics] = []

    detector.open()
    try:
        deadline = time.monotonic() + target_duration
        while time.monotonic() < deadline:
            started_at = time.monotonic()
            ok, frame = detector.read()
            if ok:
                landmarks = detector.extract_landmarks(frame)
                if landmarks is not None and required_landmarks_visible(landmarks, min_visibility=min_visibility):
                    metrics = measure_posture_metrics(landmarks)
                    if metrics.camera_distance == "ok":
                        samples.append(metrics)

            remaining = frame_interval - (time.monotonic() - started_at)
            if remaining > 0:
                time.sleep(remaining)
    finally:
        detector.close()

    if len(samples) < required_samples:
        raise RuntimeError(
            f"Kalibrovka uchun yetarli namunalar to'planmadi: {len(samples)} / {required_samples}. "
            "Kameraga to'g'ri o'tirib yana urinib ko'ring."
        )

    return build_calibration_profile(samples)


def run_detection_loop(
    signal_queue: Queue[PostureResult],
    stats_queue: Queue[PostureResult],
    stop_event: Any,
    config: dict[str, Any],
) -> None:
    fps = max(int(config.get("fps", 10)), 1)
    frame_interval = 1.0 / fps
    temporal_filter = TemporalFilter(
        window_size=int(config["temporal_window_size"]),
        threshold=float(config["temporal_threshold"]),
        cooldown_sec=float(config["cooldown_seconds"]),
    )
    sit_tracker = SitDurationTracker(
        break_threshold_sec=float(config.get("sit_break_threshold_seconds", 60.0)),
        alert_threshold_sec=float(config.get("sit_alert_threshold_seconds", 25 * 60.0)),
        cooldown_sec=float(config.get("sit_alert_cooldown_seconds", 5 * 60.0)),
    )
    gaze_tracker = EyeGazeTracker(
        gaze_alert_seconds=float(config.get("gaze_alert_seconds", 20 * 60.0)),
        break_duration_seconds=float(config.get("gaze_break_seconds", 20.0)),
        cooldown_sec=float(config.get("gaze_alert_cooldown_seconds", 60.0)),
    )
    detector = PoseDetector(config)

    try:
        detector.open()
    except Exception:
        logger.exception("Detection loop could not start")
        return

    try:
        while not stop_event.is_set():
            started_at = time.monotonic()
            ok, frame = detector.read()
            if not ok:
                logger.warning("Kameradan kadr olib bo'lmadi")
                sit_tracker.observe(person_present=False)
                if stop_event.wait(frame_interval):
                    break
                continue

            result = detector.process_frame(frame)
            person_present = not result.skipped and result.posture_score is not None
            sit_tracker.observe(person_present=person_present)
            gaze_tracker.observe(facing_screen=person_present)

            result.sit_seconds = round(sit_tracker.continuous_sit_seconds, 1)
            if result.posture_score is not None:
                result.ergonomic_score = compute_ergonomic_score(
                    result.posture_score,
                    continuous_sit_seconds=result.sit_seconds,
                    face_distance=result.face_distance,
                    continuous_gaze_seconds=gaze_tracker.continuous_gaze_seconds,
                )

            stats_queue.put(result)

            if not result.skipped and temporal_filter.update(result.status == "bad"):
                signal_queue.put(result)

            if sit_tracker.needs_break_alert():
                break_result = PostureResult(
                    status="bad",
                    issues=["Tanaffus qiling!"],
                    sit_seconds=result.sit_seconds,
                    ergonomic_score=result.ergonomic_score,
                    break_alert=True,
                )
                signal_queue.put(break_result)

            if gaze_tracker.needs_gaze_alert():
                gaze_result = PostureResult(
                    status="bad",
                    issues=["20-20-20!"],
                    sit_seconds=result.sit_seconds,
                    ergonomic_score=result.ergonomic_score,
                )
                signal_queue.put(gaze_result)

            elapsed = time.monotonic() - started_at
            remaining = frame_interval - elapsed
            if remaining > 0 and stop_event.wait(remaining):
                break
    finally:
        detector.close()
