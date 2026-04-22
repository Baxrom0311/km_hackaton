"""Posture metrikalarni landmark koordinatalaridan hisoblash.

Geometrik funksiyalar: burchaklar, masofalar, camera kompensatsiya.
Bu modul faqat matematika — kameraga yoki AI modelga bog'liq emas.
"""

from __future__ import annotations

import math
from typing import Protocol, Sequence


class LandmarkLike(Protocol):
    x: float
    y: float
    z: float
    visibility: float


# Upper-body webcam posture uchun burun, quloqlar va yelkalar yetarli.
REQUIRED_LANDMARKS = (0, 7, 8, 11, 12)


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
    return _line_angle_xy_deg(landmarks[7], landmarks[8])


def get_camera_roll_xy_deg(landmarks: Sequence[LandmarkLike]) -> float:
    return _line_angle_xy_deg(landmarks[11], landmarks[12])


def get_roll_xy_deg(landmarks: Sequence[LandmarkLike]) -> float:
    return _normalize_angle_delta_deg(
        get_raw_roll_xy_deg(landmarks),
        get_camera_roll_xy_deg(landmarks),
    )


def get_raw_yaw_xz_deg(landmarks: Sequence[LandmarkLike]) -> float:
    return _line_angle_xz_deg(landmarks[7], landmarks[8])


def get_camera_yaw_xz_deg(landmarks: Sequence[LandmarkLike]) -> float:
    return _line_angle_xz_deg(landmarks[11], landmarks[12])


def get_yaw_xz_deg(landmarks: Sequence[LandmarkLike]) -> float:
    return _normalize_angle_delta_deg(
        get_raw_yaw_xz_deg(landmarks),
        get_camera_yaw_xz_deg(landmarks),
    )


def get_pitch_yz_deg(landmarks: Sequence[LandmarkLike]) -> float:
    head_center = _average_point_3d(landmarks, (0, 7, 8))
    shoulder_center = _average_point_3d(landmarks, (11, 12))
    vec_y = head_center[1] - shoulder_center[1]
    vec_z = head_center[2] - shoulder_center[2]
    if abs(vec_y) < 1e-6 and abs(vec_z) < 1e-6:
        return 0.0
    return math.degrees(math.atan2(vec_z, -vec_y))


def get_neck_rotation(landmarks: Sequence[LandmarkLike]) -> float:
    return min(abs(get_yaw_xz_deg(landmarks)) / 20.0, 1.0)


def get_lateral_head_tilt(landmarks: Sequence[LandmarkLike]) -> float:
    return abs(get_roll_xy_deg(landmarks))


def get_shoulder_roundness(landmarks: Sequence[LandmarkLike]) -> float:
    """Yelkalar oldinga bukilganligini aniqlash (0.0..1.0).

    Ilmiy asos: Upper crossed syndrome (Janda, 1988).
    """
    shoulder_z = (landmarks[11].z + landmarks[12].z) / 2.0
    ear_z = (landmarks[7].z + landmarks[8].z) / 2.0
    diff = ear_z - shoulder_z
    if diff <= 0:
        return 0.0
    return min(diff / 0.15, 1.0)


def get_shoulder_elevation(landmarks: Sequence[LandmarkLike]) -> float:
    """Yelkalar ko'tarilishi riskini 0.0..1.0 oraliqda baholaydi.

    Quloq-yelka vertikal masofa qisqarsa, trapetsiya zo'riqishi yoki stress
    sabab yelkalar yuqoriga tortilgan bo'lishi mumkin.
    """
    ear_y = (landmarks[7].y + landmarks[8].y) / 2.0
    shoulder_y = (landmarks[11].y + landmarks[12].y) / 2.0
    vertical_span = shoulder_y - ear_y
    if vertical_span >= 0.16:
        return 0.0
    if vertical_span <= 0.08:
        return 1.0
    return (0.16 - vertical_span) / 0.08


def estimate_camera_angle(landmarks: Sequence[LandmarkLike]) -> float:
    """Kamera burchagini taxminiy aniqlash (gradus)."""
    ear_y = (landmarks[7].y + landmarks[8].y) / 2.0
    shoulder_y = (landmarks[11].y + landmarks[12].y) / 2.0
    vertical_span = shoulder_y - ear_y
    if vertical_span < 0.02:
        return 45.0
    if vertical_span > 0.35:
        return -20.0
    deviation = abs(vertical_span - 0.15)
    return min(deviation * 200, 40.0)


def check_camera_distance(landmarks: Sequence[LandmarkLike]) -> str:
    distance = abs(landmarks[11].x - landmarks[12].x)
    if distance < 0.08:
        return "too_far"
    if distance > 0.70:
        return "too_close"
    return "ok"
