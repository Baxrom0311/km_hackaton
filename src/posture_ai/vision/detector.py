from __future__ import annotations

import importlib.util
import logging
import math
import statistics
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from queue import Queue
from typing import Any, Protocol, Sequence

from posture_ai.core.ergonomics import (
    EyeGazeTracker,
    SitDurationTracker,
    compute_ergonomic_score,
    estimate_face_camera_distance,
    eye_strain_risk,
    is_facing_camera,
)
from posture_ai.core.filter import TemporalFilter

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
    roll_xy_deg: float = 0.0         # camera-compensated frontal plane / XY
    yaw_xz_deg: float = 0.0          # camera-compensated horizontal plane / XZ
    pitch_yz_deg: float = 0.0        # sagittal plane / YZ
    camera_roll_xy_deg: float = 0.0  # kamera/torso ko'rinish roll burchagi
    camera_yaw_xz_deg: float = 0.0   # kamera/torso yon ko'rinish burchagi
    camera_pitch_yz_deg: float = 0.0 # kamera baland/past ko'rinish burchagi
    neck_rotation: float = 0.0        # bo'yin burilish darajasi (0 = to'g'ri)
    lateral_head_tilt: float = 0.0    # bosh yon qiyshayishi (gradus)
    shoulder_roundness: float = 0.0   # yelkalar oldinga bukilganligi (0..1)
    camera_angle: float = 0.0         # kamera burchagi (gradus, 0=to'g'ri)


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
    camera_angle: float | None = None


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


def _average_point_3d(
    landmarks: Sequence[LandmarkLike],
    indexes: Sequence[int],
) -> tuple[float, float, float]:
    total_x = 0.0
    total_y = 0.0
    total_z = 0.0
    for index in indexes:
        total_x += landmarks[index].x
        total_y += landmarks[index].y
        total_z += landmarks[index].z
    count = float(len(indexes))
    return total_x / count, total_y / count, total_z / count


def _normalize_angle_delta_deg(value: float, reference: float) -> float:
    """Ikki burchak farqini -180..180 oraliqqa keltiradi."""
    delta = value - reference
    while delta > 180.0:
        delta -= 360.0
    while delta < -180.0:
        delta += 360.0
    return delta


def _line_angle_xy_deg(a: LandmarkLike, b: LandmarkLike) -> float:
    dx = b.x - a.x
    dy = b.y - a.y
    if abs(dx) < 1e-6 and abs(dy) < 1e-6:
        return 0.0
    return math.degrees(math.atan2(dy, dx))


def _line_angle_xz_deg(a: LandmarkLike, b: LandmarkLike) -> float:
    dx = b.x - a.x
    dz = b.z - a.z
    if abs(dx) < 1e-6 and abs(dz) < 1e-6:
        return 0.0
    return math.degrees(math.atan2(dz, dx))


def required_landmarks_visible(landmarks: Sequence[LandmarkLike], min_visibility: float = 0.5) -> bool:
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


def get_raw_roll_xy_deg(landmarks: Sequence[LandmarkLike]) -> float:
    """Kamera kompensatsiyasiz bosh roll burchagi."""
    return _line_angle_xy_deg(landmarks[7], landmarks[8])


def get_camera_roll_xy_deg(landmarks: Sequence[LandmarkLike]) -> float:
    """Kamera/odam ko'rinishidagi in-plane roll burchagi.

    Laptop kamerasi yoki ekran qiyshiq tursa, quloqlar ham, yelkalar ham bir
    tomonga og'adi. Shu sababli yelka chizig'i view baseline sifatida olinadi.
    """
    return _line_angle_xy_deg(landmarks[11], landmarks[12])


def get_roll_xy_deg(landmarks: Sequence[LandmarkLike]) -> float:
    """XY tekislikdagi yon qiyshayish, kamera roll burchagidan kompensatsiya qilingan."""
    return _normalize_angle_delta_deg(
        get_raw_roll_xy_deg(landmarks),
        get_camera_roll_xy_deg(landmarks),
    )


def get_raw_yaw_xz_deg(landmarks: Sequence[LandmarkLike]) -> float:
    """Kamera kompensatsiyasiz bosh yaw burchagi."""
    return _line_angle_xz_deg(landmarks[7], landmarks[8])


def get_camera_yaw_xz_deg(landmarks: Sequence[LandmarkLike]) -> float:
    """Kamera/odam yon burchagini yelkalar chuqurligi orqali taxmin qiladi."""
    return _line_angle_xz_deg(landmarks[11], landmarks[12])


def get_yaw_xz_deg(landmarks: Sequence[LandmarkLike]) -> float:
    """XZ tekislikdagi bo'yin burilishi, kamera/torso yaw baseline'dan kompensatsiya qilingan."""
    return _normalize_angle_delta_deg(
        get_raw_yaw_xz_deg(landmarks),
        get_camera_yaw_xz_deg(landmarks),
    )


def get_pitch_yz_deg(landmarks: Sequence[LandmarkLike]) -> float:
    """YZ tekislikdagi oldinga/orqaga pitch burchagi."""
    head_center = _average_point_3d(landmarks, (0, 7, 8))
    shoulder_center = _average_point_3d(landmarks, (11, 12))
    vec_y = head_center[1] - shoulder_center[1]
    vec_z = head_center[2] - shoulder_center[2]
    if abs(vec_y) < 1e-6 and abs(vec_z) < 1e-6:
        return 0.0
    return math.degrees(math.atan2(vec_z, -vec_y))


def get_neck_rotation(landmarks: Sequence[LandmarkLike]) -> float:
    """0..1 oraliqdagi yaw risk ko'rsatkichi."""
    return min(abs(get_yaw_xz_deg(landmarks)) / 20.0, 1.0)


def get_lateral_head_tilt(landmarks: Sequence[LandmarkLike]) -> float:
    """Graduslarda lateral tilt, XY burchakdan olinadi."""
    return abs(get_roll_xy_deg(landmarks))


def get_shoulder_roundness(landmarks: Sequence[LandmarkLike]) -> float:
    """Yelkalar oldinga bukilganligini (slouch/rounded shoulders) aniqlash.

    Yelkalar (11, 12) ning Z-koordinatasini quloqlar (7, 8) bilan solishtiradi.
    Agar yelkalar quloqlardan oldinda bo'lsa → rounded shoulders.
    Qaytadi: 0.0 (to'g'ri) .. 1.0 (juda bukilgan)
    Ilmiy asos: Rounded shoulders — upper crossed syndrome (Janda, 1988)
    """
    shoulder_z = (landmarks[11].z + landmarks[12].z) / 2.0
    ear_z = (landmarks[7].z + landmarks[8].z) / 2.0
    # MediaPipe: manfiy Z = kameraga yaqin
    # Yelkalar quloqlardan kameraga yaqinroq (z < ear_z) → slouch
    # diff > 0 = yelkalar oldinda (slouch)
    diff = ear_z - shoulder_z
    if diff <= 0:
        return 0.0  # Normal — yelkalar quloqlar bilan bir tekisda yoki orqada
    return min(diff / 0.15, 1.0)


def estimate_camera_angle(landmarks: Sequence[LandmarkLike]) -> float:
    """Kamera burchagini taxminiy aniqlash (gradus).

    Yelkalar va quloqlar orasidagi Y-nisbatga qaraydi.
    - To'g'ri (0°): yelkalar quloqlardan pastda, normal masofa
    - Yuqoridan (>20°): yelkalar ko'rinmas yoki juda past
    - 45° burchak: yelka-quloq Y-masofa juda katta

    Bu burchak threshold'larni moslashtirish uchun ishlatiladi.
    """
    ear_y = (landmarks[7].y + landmarks[8].y) / 2.0
    shoulder_y = (landmarks[11].y + landmarks[12].y) / 2.0
    nose_y = landmarks[0].y

    # Normal holatda: ear_y < shoulder_y (quloqlar tepada, yelkalar pastda)
    # Yuqoridan kamera: ear_y va shoulder_y juda yaqin
    # Pastdan kamera: ear_y >> shoulder_y
    vertical_span = shoulder_y - ear_y
    if vertical_span < 0.02:
        # Kamera tepadan — yelka va quloq bir tekisda
        return 45.0
    if vertical_span > 0.35:
        # Kamera pastdan — yelkalar juda pastda
        return -20.0
    # Normal range: 0.05..0.25
    # 0.15 = ideal to'g'ri kamera
    deviation = abs(vertical_span - 0.15)
    return min(deviation * 200, 40.0)  # 0..40 gradus


def check_camera_distance(landmarks: Sequence[LandmarkLike]) -> str:
    """Kameradagi foydalanuvchi masofasini tekshirish.

    Yelkalar orasidagi X-masofa orqali odam qanchalik yaqin/uzoq ekanini aniqlaydi.
    """
    distance = abs(landmarks[11].x - landmarks[12].x)
    if distance < 0.08:    # juda uzoq — yelkalar ko'rinmaydi
        return "too_far"
    if distance > 0.70:    # juda yaqin — faqat yuz ko'rinadi
        return "too_close"
    return "ok"


def measure_posture_metrics(landmarks: Sequence[LandmarkLike]) -> PostureMetrics:
    camera_roll_xy_deg = get_camera_roll_xy_deg(landmarks)
    camera_yaw_xz_deg = get_camera_yaw_xz_deg(landmarks)
    camera_pitch_yz_deg = estimate_camera_angle(landmarks)
    roll_xy_deg = get_roll_xy_deg(landmarks)
    yaw_xz_deg = get_yaw_xz_deg(landmarks)
    pitch_yz_deg = get_pitch_yz_deg(landmarks)
    return PostureMetrics(
        head_angle=get_head_tilt_angle(landmarks),
        shoulder_diff=get_shoulder_symmetry(landmarks),
        forward_lean=get_forward_lean(landmarks),
        camera_distance=check_camera_distance(landmarks),
        roll_xy_deg=roll_xy_deg,
        yaw_xz_deg=yaw_xz_deg,
        pitch_yz_deg=pitch_yz_deg,
        camera_roll_xy_deg=camera_roll_xy_deg,
        camera_yaw_xz_deg=camera_yaw_xz_deg,
        camera_pitch_yz_deg=camera_pitch_yz_deg,
        neck_rotation=min(abs(yaw_xz_deg) / 20.0, 1.0),
        lateral_head_tilt=abs(roll_xy_deg),
        shoulder_roundness=get_shoulder_roundness(landmarks),
        camera_angle=camera_pitch_yz_deg,
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
    penalty = (
        (risk_head * 15.0)
        + (risk_shoulder * 10.0)
        + (risk_forward * 10.0)
        + (risk_pitch * 20.0)
        + (risk_yaw * 15.0)
        + (risk_roll * 10.0)
        + (risk_slouch * 20.0)
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


def analyze_posture(
    landmarks: Sequence[LandmarkLike],
    *,
    head_angle_threshold: float = 25.0,
    shoulder_diff_threshold: float = 0.07,
    forward_lean_threshold: float = -0.2,
    roll_xy_threshold_deg: float = 12.0,
    yaw_xz_threshold_deg: float = 18.0,
    pitch_yz_threshold_deg: float = 18.0,
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

    # Kamera masofasi — skip qilmaslik, lekin issue sifatida qo'shish
    # Foydalanuvchi juda uzoq/yaqin bo'lsa ham posture tekshirilsin
    camera_dist_issue: str | None = None
    if metrics.camera_distance == "too_close":
        camera_dist_issue = "Ekranga juda yaqinsiz!"
    elif metrics.camera_distance == "too_far":
        camera_dist_issue = "Ekrandan juda uzoqsiz!"

    # Kamera burchagi kompensatsiyasi.
    # Single webcam'da odam 30-45° yon yoki kamera biroz qiyshiq ko'rinsa,
    # raw landmark burchaklar kattalashadi. View angle katta bo'lganda threshold
    # yumshatiladi, roll/yaw esa yuqorida torso baseline'dan kompensatsiya qilingan.
    camera_view_angle = max(
        abs(metrics.camera_roll_xy_deg),
        abs(metrics.camera_yaw_xz_deg),
        abs(metrics.camera_pitch_yz_deg),
    )
    angle_factor = 1.0
    if camera_view_angle > 15.0:
        # Kamera burchagi oshgan sari thresholdlar yumshatiladi
        angle_factor = 1.0 + (camera_view_angle - 15.0) * 0.02
        angle_factor = min(angle_factor, 1.8)

    # Kalibrovka bo'lsa, thresholdlarni baseline'ga nisbatan moslashtirish
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

    # ═══ ASOSIY 3 TA HOLAT (mavjud) ═══
    if metrics.head_angle > effective_head_threshold:
        issues.append("Boshingizni ko'taring!")

    # Kamera/laptop 25°+ in-plane qiyshaygan bo'lsa, yelka balandligi ham
    # perspektivadan noto'g'ri ko'rinadi. Bunday holatda posture emas, camera
    # setup muammosi sifatida qaytaramiz.
    camera_roll_reliable = abs(metrics.camera_roll_xy_deg) <= 25.0
    if camera_roll_reliable and metrics.shoulder_diff > effective_shoulder_threshold:
        issues.append("Yelkalaringizni tekislang!")
    lean_back_threshold = 0.1 * angle_factor
    is_forward_bad = (
        metrics.forward_lean < effective_forward_threshold
        or metrics.pitch_yz_deg <= -effective_pitch_threshold
    )
    is_back_bad = (
        metrics.forward_lean > lean_back_threshold
        or metrics.pitch_yz_deg >= effective_pitch_threshold
    )

    if is_forward_bad:
        issues.append("Oldinga engashmang!")

    # ═══ YANGI HOLATLAR ═══

    # 4. Orqaga yotib olish (lean back)
    if is_back_bad and not is_forward_bad:
        issues.append("Orqaga yotmang!")

    # 5. XZ tekislikdagi burilish (yaw)
    if abs(metrics.yaw_xz_deg) > effective_yaw_threshold:
        issues.append("Bo'yningizni to'g'rilang!")

    # 6. XY tekislikdagi qiyshayish (roll)
    if abs(metrics.roll_xy_deg) > effective_roll_threshold:
        issues.append("Boshingiz qiyshaygan!")

    # 7. Yelkalar oldinga bukilgan (rounded shoulders / slouch)
    slouch_threshold = 0.5  # 0..1 oraliq, 0.5+ = sezilarli
    if metrics.shoulder_roundness > slouch_threshold:
        issues.append("Yelkalaringizni oching!")

    # 8. Ko'z zo'riqishi — ekranga yaqin
    face_distance = estimate_face_camera_distance(landmarks)
    if eye_strain_risk(face_distance) >= 0.75:
        issues.append("Ekranga yaqin!")

    # 9. Ekrandan juda uzoq
    if eye_strain_risk(face_distance) == 0.0 and face_distance < 0.10:
        issues.append("Ekrandan juda uzoqsiz!")

    # 10. Kamera masofasi muammosi (agar bor bo'lsa)
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

        # Past resolution — CPU yuklamasini 3-4x kamaytiradi
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

    def _prepare_frame_for_ai(self, frame: Any) -> Any:
        """AI inferensiya yukini kamaytirish uchun frame'ni kichraytiradi."""
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

    def process_frame(self, frame: Any) -> PostureResult:
        landmarks = self.extract_landmarks(frame)
        if landmarks is None:
            return PostureResult(status="unknown", skipped=True, reason="no_pose")

        return analyze_posture(
            landmarks,
            head_angle_threshold=float(self.config["head_angle_threshold"]),
            shoulder_diff_threshold=float(self.config["shoulder_diff_threshold"]),
            forward_lean_threshold=float(self.config["forward_lean_threshold"]),
            roll_xy_threshold_deg=float(self.config.get("roll_xy_threshold_deg", 12.0)),
            yaw_xz_threshold_deg=float(self.config.get("yaw_xz_threshold_deg", 18.0)),
            pitch_yz_threshold_deg=float(self.config.get("pitch_yz_threshold_deg", 18.0)),
            min_visibility=float(self.config.get("min_visibility", 0.7)),
            baseline_head_angle=self.config.get("baseline_head_angle"),
            baseline_shoulder_diff=self.config.get("baseline_shoulder_diff"),
            baseline_forward_lean=self.config.get("baseline_forward_lean"),
            baseline_roll_xy_deg=self.config.get("baseline_roll_xy_deg"),
            baseline_yaw_xz_deg=self.config.get("baseline_yaw_xz_deg"),
            baseline_pitch_yz_deg=self.config.get("baseline_pitch_yz_deg"),
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
            gaze_tracker.observe(facing_screen=bool(result.facing_camera) if person_present else False)

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
