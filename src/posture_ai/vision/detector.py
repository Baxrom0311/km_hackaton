"""PoseDetector va posture analiz moduli.

Kamera bilan ishlash, MediaPipe orqali landmark aniqlash,
va posture tahlili shu yerda amalga oshiriladi.

Geometrik funksiyalar: vision.metrics
Scoring va calibration: vision.scoring
"""

from __future__ import annotations

import importlib.util

import sys
import time
from queue import Queue
from typing import Any, Sequence

from posture_ai.core.config import resolve_model_asset_path
from posture_ai.core.ergonomics import (
    estimate_face_camera_distance,
    eye_strain_risk,
    is_facing_camera,
)
from posture_ai.core.logger import logger
from posture_ai.core.session import SessionProcessor
from posture_ai.vision.metrics import (
    REQUIRED_LANDMARKS,
    LandmarkLike,
    required_landmarks_visible,
)
from posture_ai.vision.scoring import (
    PostureMetrics,
    PostureResult,
    build_calibration_profile,
    calculate_posture_score,
    measure_posture_metrics,
)

# Re-export for backward compatibility
__all__ = [
    "REQUIRED_LANDMARKS",
    "LandmarkLike",
    "PostureMetrics",
    "PostureResult",
    "DependencyUnavailableError",
    "PoseDetector",
    "analyze_posture",
    "build_calibration_profile",
    "calculate_posture_score",
    "check_runtime_dependencies",
    "collect_calibration_profile",
    "measure_posture_metrics",
    "required_landmarks_visible",
    "run_detection_loop",
]

class DependencyUnavailableError(RuntimeError):
    pass


def check_runtime_dependencies() -> list[str]:
    missing: list[str] = []
    for module_name in ("cv2", "mediapipe", "PySide6"):
        if importlib.util.find_spec(module_name) is None:
            missing.append(module_name)
    return missing


def analyze_posture(
    landmarks: Sequence[LandmarkLike],
    *,
    head_angle_threshold: float = 25.0,
    shoulder_diff_threshold: float = 0.07,
    forward_lean_threshold: float = -0.2,
    roll_xy_threshold_deg: float = 12.0,
    yaw_xz_threshold_deg: float = 18.0,
    pitch_yz_threshold_deg: float = 18.0,
    shoulder_elevation_threshold: float = 0.75,
    min_visibility: float = 0.5,
    baseline_head_angle: float | None = None,
    baseline_shoulder_diff: float | None = None,
    baseline_forward_lean: float | None = None,
    baseline_roll_xy_deg: float | None = None,
    baseline_yaw_xz_deg: float | None = None,
    baseline_pitch_yz_deg: float | None = None,
) -> PostureResult:
    if not required_landmarks_visible(landmarks, min_visibility=min_visibility):
        return PostureResult(status="unknown", skipped=True, reason="low_visibility")

    metrics = measure_posture_metrics(landmarks)

    camera_dist_issue: str | None = None
    if metrics.camera_distance == "too_close":
        camera_dist_issue = "Ekranga juda yaqinsiz!"
    elif metrics.camera_distance == "too_far":
        camera_dist_issue = "Ekrandan juda uzoqsiz!"

    camera_view_angle = max(
        abs(metrics.camera_roll_xy_deg),
        abs(metrics.camera_yaw_xz_deg),
        abs(metrics.camera_pitch_yz_deg),
    )
    angle_factor = 1.0
    if camera_view_angle > 15.0:
        angle_factor = 1.0 + (camera_view_angle - 15.0) * 0.02
        angle_factor = min(angle_factor, 1.8)

    effective_head_threshold = head_angle_threshold * angle_factor
    effective_shoulder_threshold = shoulder_diff_threshold * angle_factor
    effective_forward_threshold = forward_lean_threshold / angle_factor
    effective_roll_threshold = roll_xy_threshold_deg * angle_factor
    effective_yaw_threshold = yaw_xz_threshold_deg * angle_factor
    effective_pitch_threshold = pitch_yz_threshold_deg * angle_factor

    if baseline_head_angle is not None:
        effective_head_threshold = max(baseline_head_angle + 8.0, 18.0) * angle_factor
    if baseline_shoulder_diff is not None:
        effective_shoulder_threshold = max(baseline_shoulder_diff + 0.02, 0.03) * angle_factor
    if baseline_forward_lean is not None:
        effective_forward_threshold = min(baseline_forward_lean - 0.12, -0.08) / angle_factor
    if baseline_roll_xy_deg is not None:
        effective_roll_threshold = max(abs(baseline_roll_xy_deg) + 6.0, 8.0) * angle_factor
    if baseline_yaw_xz_deg is not None:
        effective_yaw_threshold = max(abs(baseline_yaw_xz_deg) + 8.0, 10.0) * angle_factor
    if baseline_pitch_yz_deg is not None:
        effective_pitch_threshold = max(abs(baseline_pitch_yz_deg) + 8.0, 10.0) * angle_factor

    issues: list[str] = []
    facing_camera = is_facing_camera(landmarks)

    if metrics.head_angle > effective_head_threshold:
        issues.append("Boshingizni ko'taring!")

    camera_roll_reliable = abs(metrics.camera_roll_xy_deg) <= 25.0
    if camera_roll_reliable and metrics.shoulder_diff > effective_shoulder_threshold:
        issues.append("Yelkalaringizni tekislang!")

    lean_back_threshold = 0.06 * angle_factor
    if baseline_forward_lean is not None:
        lean_back_threshold = max(float(baseline_forward_lean) + 0.14, 0.05) * angle_factor
    is_forward_bad = (
        metrics.forward_lean < effective_forward_threshold
        or metrics.pitch_yz_deg <= -effective_pitch_threshold
    )
    is_back_bad = (
        metrics.forward_lean > lean_back_threshold
        or metrics.pitch_yz_deg >= (effective_pitch_threshold * 0.85)
    )

    if is_forward_bad:
        issues.append("Oldinga engashmang!")

    if is_back_bad and not is_forward_bad:
        issues.append("Orqaga yotmang!")

    if abs(metrics.yaw_xz_deg) > effective_yaw_threshold:
        issues.append("Bo'yningizni to'g'rilang!")

    if abs(metrics.roll_xy_deg) > effective_roll_threshold:
        issues.append("Boshingiz qiyshaygan!")

    slouch_threshold = 0.5
    if metrics.shoulder_roundness > slouch_threshold:
        issues.append("Yelkalaringizni oching!")

    if metrics.shoulder_elevation > shoulder_elevation_threshold:
        issues.append("Yelkangizni bo'shashtiring!")

    face_distance = estimate_face_camera_distance(landmarks)
    if eye_strain_risk(face_distance) >= 0.75:
        issues.append("Ekranga yaqin!")

    if eye_strain_risk(face_distance) == 0.0 and face_distance < 0.10:
        issues.append("Ekrandan juda uzoqsiz!")

    if camera_dist_issue and not (
        camera_dist_issue == "Ekranga juda yaqinsiz!" and "Ekranga yaqin!" in issues
    ):
        issues.append(camera_dist_issue)

    if abs(metrics.camera_roll_xy_deg) > 35.0:
        issues.append("Kamera qiyshaygan, uni tekislang!")
    if abs(metrics.camera_yaw_xz_deg) > 60.0:
        issues.append("Kamerani yuzingizga yaqinroq to'g'rilang!")
    if abs(metrics.camera_pitch_yz_deg) > 32.0:
        issues.append("Kamerani ko'z darajasiga qo'ying!")

    issues = list(dict.fromkeys(issues))

    posture_score = calculate_posture_score(
        metrics,
        head_angle_threshold=effective_head_threshold,
        shoulder_diff_threshold=effective_shoulder_threshold,
        forward_lean_threshold=effective_forward_threshold,
        roll_xy_threshold_deg=effective_roll_threshold,
        yaw_xz_threshold_deg=effective_yaw_threshold,
        pitch_yz_threshold_deg=effective_pitch_threshold,
        baseline_head_angle=baseline_head_angle,
        baseline_shoulder_diff=baseline_shoulder_diff,
        baseline_forward_lean=baseline_forward_lean,
        baseline_roll_xy_deg=baseline_roll_xy_deg,
        baseline_yaw_xz_deg=baseline_yaw_xz_deg,
        baseline_pitch_yz_deg=baseline_pitch_yz_deg,
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
        facing_camera=facing_camera,
        roll_xy_deg=round(metrics.roll_xy_deg, 1),
        yaw_xz_deg=round(metrics.yaw_xz_deg, 1),
        pitch_yz_deg=round(metrics.pitch_yz_deg, 1),
        shoulder_elevation=round(metrics.shoulder_elevation, 3),
        spine_score=metrics.spine_score,
        camera_roll_xy_deg=round(metrics.camera_roll_xy_deg, 1),
        camera_yaw_xz_deg=round(metrics.camera_yaw_xz_deg, 1),
        camera_pitch_yz_deg=round(metrics.camera_pitch_yz_deg, 1),
        neck_rotation=round(metrics.neck_rotation, 3),
        lateral_head_tilt=round(metrics.lateral_head_tilt, 1),
        camera_angle=round(metrics.camera_angle, 1),
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

        camera_index = int(self.config["camera_index"])
        if sys.platform == "darwin" and hasattr(self.cv2, "CAP_AVFOUNDATION"):
            self.capture = self.cv2.VideoCapture(camera_index, self.cv2.CAP_AVFOUNDATION)
            if not self.capture.isOpened():
                self.capture.release()
                self.capture = self.cv2.VideoCapture(camera_index)
        else:
            self.capture = self.cv2.VideoCapture(camera_index)

        cam_w = int(self.config.get("camera_width", 640))
        cam_h = int(self.config.get("camera_height", 480))
        cam_fps = int(self.config.get("fps", 30))
        self.capture.set(self.cv2.CAP_PROP_FRAME_WIDTH, cam_w)
        self.capture.set(self.cv2.CAP_PROP_FRAME_HEIGHT, cam_h)
        self.capture.set(self.cv2.CAP_PROP_FPS, cam_fps)
        if hasattr(self.cv2, "CAP_PROP_BUFFERSIZE"):
            self.capture.set(self.cv2.CAP_PROP_BUFFERSIZE, 1)
        if not self.capture.isOpened():
            self.capture.release()
            self.capture = None
            raise RuntimeError("Kamerani ochib bo'lmadi. `camera_index` ni tekshiring.")

        if self.backend == "tasks":
            model_path = resolve_model_asset_path(
                str(self.config.get("model_asset_path", "models/pose_landmarker_heavy.task"))
            )
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

    def _prepare_frame_for_ai(self, frame: Any) -> Any:
        target_width = int(self.config.get("ai_frame_width", 480))
        height, width = frame.shape[:2]
        if width <= target_width:
            return frame
        target_height = max(1, int(round(height * (target_width / width))))
        return self.cv2.resize(frame, (target_width, target_height), interpolation=self.cv2.INTER_AREA)

    def extract_landmarks(self, frame: Any) -> Sequence[LandmarkLike] | None:
        if self.pose is None:
            raise RuntimeError("Pose model is not initialized")

        ai_frame = self._prepare_frame_for_ai(frame)
        rgb_frame = self.cv2.cvtColor(ai_frame, self.cv2.COLOR_BGR2RGB)
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

    def analyze_landmarks(self, landmarks: Sequence[LandmarkLike]) -> PostureResult:
        return analyze_posture(
            landmarks,
            head_angle_threshold=float(self.config["head_angle_threshold"]),
            shoulder_diff_threshold=float(self.config["shoulder_diff_threshold"]),
            forward_lean_threshold=float(self.config["forward_lean_threshold"]),
            roll_xy_threshold_deg=float(self.config.get("roll_xy_threshold_deg", 12.0)),
            yaw_xz_threshold_deg=float(self.config.get("yaw_xz_threshold_deg", 18.0)),
            pitch_yz_threshold_deg=float(self.config.get("pitch_yz_threshold_deg", 18.0)),
            shoulder_elevation_threshold=float(self.config.get("shoulder_elevation_threshold", 0.75)),
            min_visibility=float(self.config.get("min_visibility", 0.7)),
            baseline_head_angle=self.config.get("baseline_head_angle"),
            baseline_shoulder_diff=self.config.get("baseline_shoulder_diff"),
            baseline_forward_lean=self.config.get("baseline_forward_lean"),
            baseline_roll_xy_deg=self.config.get("baseline_roll_xy_deg"),
            baseline_yaw_xz_deg=self.config.get("baseline_yaw_xz_deg"),
            baseline_pitch_yz_deg=self.config.get("baseline_pitch_yz_deg"),
        )

    def process_frame(self, frame: Any) -> PostureResult:
        landmarks = self.extract_landmarks(frame)
        if landmarks is None:
            return PostureResult(status="unknown", skipped=True, reason="no_pose")

        return self.analyze_landmarks(landmarks)


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
    from posture_ai.core.filter import TemporalFilter
    from posture_ai.core.ergonomics import SitDurationTracker, EyeGazeTracker, FatigueSignalTracker

    fps = max(int(config.get("fps", 10)), 1)
    frame_interval = 1.0 / fps

    session = SessionProcessor(
        temporal_filter=TemporalFilter(
            window_size=int(config["temporal_window_size"]),
            threshold=float(config["temporal_threshold"]),
            cooldown_sec=float(config["cooldown_seconds"]),
        ),
        sit_tracker=SitDurationTracker(
            break_threshold_sec=float(config.get("sit_break_threshold_seconds", 60.0)),
            alert_threshold_sec=float(config.get("sit_alert_threshold_seconds", 25 * 60.0)),
            cooldown_sec=float(config.get("sit_alert_cooldown_seconds", 5 * 60.0)),
        ),
        gaze_tracker=EyeGazeTracker(
            gaze_alert_seconds=float(config.get("gaze_alert_seconds", 20 * 60.0)),
            break_duration_seconds=float(config.get("gaze_break_seconds", 20.0)),
            cooldown_sec=float(config.get("gaze_alert_cooldown_seconds", 60.0)),
        ),
        fatigue_signal_tracker=FatigueSignalTracker(),
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
                session.sit_tracker.observe(person_present=False)
                if stop_event.wait(frame_interval):
                    break
                continue

            result = detector.process_frame(frame)
            alerts = session.process(result)

            stats_queue.put(result)

            for alert_event in alerts:
                signal_queue.put(alert_event.result)

            elapsed = time.monotonic() - started_at
            remaining = frame_interval - elapsed
            if remaining > 0 and stop_event.wait(remaining):
                break
    finally:
        detector.close()
