from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from typing import Callable, Sequence


@dataclass(slots=True)
class SitDurationTracker:
    """Foydalanuvchi uzluksiz o'tirgan vaqtni kuzatadi.

    Kamera oldida pose aniqlanganda timer ishga tushadi. `break_threshold_sec`
    davomida pose ko'rinmasa (turib ketgan deb hisoblanadi), timer reset qilinadi.
    """

    break_threshold_sec: float = 60.0
    alert_threshold_sec: float = 25 * 60.0  # 25 daqiqa = Pomodoro stand-up
    cooldown_sec: float = 5 * 60.0  # alert oraliq
    time_fn: Callable[[], float] = time.monotonic
    sit_started_at: float | None = field(default=None, init=False)
    last_seen_at: float | None = field(default=None, init=False)
    last_alert_at: float = field(default=float("-inf"), init=False)

    def observe(self, *, person_present: bool) -> None:
        now = self.time_fn()
        if person_present:
            if self.sit_started_at is None:
                self.sit_started_at = now
            self.last_seen_at = now
            return

        if self.sit_started_at is not None and self.last_seen_at is not None:
            if (now - self.last_seen_at) >= self.break_threshold_sec:
                self.sit_started_at = None
                self.last_seen_at = None

    @property
    def continuous_sit_seconds(self) -> float:
        if self.sit_started_at is None:
            return 0.0
        return max(0.0, self.time_fn() - self.sit_started_at)

    def needs_break_alert(self) -> bool:
        sit_sec = self.continuous_sit_seconds
        if sit_sec < self.alert_threshold_sec:
            return False
        now = self.time_fn()
        if (now - self.last_alert_at) < self.cooldown_sec:
            return False
        self.last_alert_at = now
        return True


def estimate_face_camera_distance(landmarks: Sequence) -> float:
    """Yuz kamerasiga nisbatan masofani 0.0..1.0 oraliqda qaytaradi.

    Asos: yuz landmarklari (chap-o'ng quloq) orasidagi gorizontal masofa.
    Yaqinroq bo'lsa qiymat kattalashadi (kameraga yaqin → ko'z zo'riqishi xavfi).
    """
    left_ear_x = landmarks[7].x
    right_ear_x = landmarks[8].x
    return abs(left_ear_x - right_ear_x)


def eye_strain_risk(
    face_distance: float,
    *,
    safe_max: float = 0.18,
    danger_min: float = 0.32,
) -> float:
    """Ko'z zo'riqishi xavfini 0..1 oraliqda baholaydi.

    `safe_max` dan kichik — xavf yo'q (0.0).
    `danger_min` va undan katta — yuqori xavf (1.0).
    Oraliqda — chiziqli o'sish.
    """
    if face_distance <= safe_max:
        return 0.0
    if face_distance >= danger_min:
        return 1.0
    span = danger_min - safe_max
    return (face_distance - safe_max) / span


def sit_duration_risk(
    continuous_sit_seconds: float,
    *,
    comfort_max_seconds: float = 25 * 60.0,
    danger_min_seconds: float = 90 * 60.0,
) -> float:
    """O'tirish davomiyligi xavfini 0..1 oraliqda baholaydi.

    25 daqiqagacha — xavfsiz; 90 daqiqa va undan ko'p — yuqori xavf.
    """
    if continuous_sit_seconds <= comfort_max_seconds:
        return 0.0
    if continuous_sit_seconds >= danger_min_seconds:
        return 1.0
    span = danger_min_seconds - comfort_max_seconds
    return (continuous_sit_seconds - comfort_max_seconds) / span


def is_facing_camera(landmarks: Sequence, threshold: float = 0.12) -> bool:
    """Foydalanuvchi kameraga qarayotganini aniqlaydi.

    Burun (0) va quloqlar (7, 8) orasidagi X-simmetriyani tekshiradi.
    Agar burun chap va o'ng quloq orasida markazlashgan bo'lsa → ekranga qarayapti.
    """
    nose_x = landmarks[0].x
    left_ear_x = landmarks[7].x
    right_ear_x = landmarks[8].x
    mid_x = (left_ear_x + right_ear_x) / 2.0
    return abs(nose_x - mid_x) < threshold


@dataclass(slots=True)
class EyeGazeTracker:
    """Foydalanuvchining ekranga uzluksiz tikilish vaqtini kuzatadi.

    20-20-20 qoidasi: har 20 daqiqada, 20 soniya, 20 futga (6 m) uzoqqa qarang.
    Agar foydalanuvchi `gaze_alert_seconds` davomida uzluksiz ekranga
    qarasa, ogohlantirish beriladi.
    """

    gaze_alert_seconds: float = 20 * 60.0  # 20 daqiqa
    break_duration_seconds: float = 20.0   # 20 sek tanaffus
    cooldown_sec: float = 60.0
    time_fn: Callable[[], float] = time.monotonic
    gaze_started_at: float | None = field(default=None, init=False)
    last_seen_at: float | None = field(default=None, init=False)
    last_alert_at: float = field(default=float("-inf"), init=False)

    def observe(self, *, facing_screen: bool) -> None:
        now = self.time_fn()
        if facing_screen:
            if self.gaze_started_at is None:
                self.gaze_started_at = now
            self.last_seen_at = now
            return

        # Yuzini burmasa break_duration_seconds kutadi, keyin reset
        if self.gaze_started_at is not None and self.last_seen_at is not None:
            if (now - self.last_seen_at) >= self.break_duration_seconds:
                self.gaze_started_at = None
                self.last_seen_at = None

    @property
    def continuous_gaze_seconds(self) -> float:
        if self.gaze_started_at is None:
            return 0.0
        return max(0.0, self.time_fn() - self.gaze_started_at)

    def needs_gaze_alert(self) -> bool:
        gaze_sec = self.continuous_gaze_seconds
        if gaze_sec < self.gaze_alert_seconds:
            return False
        now = self.time_fn()
        if (now - self.last_alert_at) < self.cooldown_sec:
            return False
        self.last_alert_at = now
        return True


def compute_ergonomic_score(
    posture_score: float,
    *,
    continuous_sit_seconds: float,
    face_distance: float | None,
    continuous_gaze_seconds: float = 0.0,
    sit_weight: float = 0.25,
    eye_weight: float = 0.15,
    gaze_weight: float = 0.10,
) -> int:
    """Posture, o'tirish vaqti, ko'z masofasi va gaze vaqti asosida 0..100 ergonomik ball.

    Yuqoriroq ball — yaxshi ergonomika. Posture score asos sifatida
    olinadi, sit-duration, eye-strain va gaze-time xavflari penalti sifatida ayriladi.
    """
    base = max(0.0, min(100.0, float(posture_score)))
    sit_penalty = sit_duration_risk(continuous_sit_seconds) * 100.0 * sit_weight
    eye_penalty = (
        eye_strain_risk(face_distance) * 100.0 * eye_weight
        if face_distance is not None
        else 0.0
    )
    # Gaze penalty: 20 daqiqagacha 0, 60 daqiqada max
    gaze_risk = sit_duration_risk(
        continuous_gaze_seconds,
        comfort_max_seconds=20 * 60.0,
        danger_min_seconds=60 * 60.0,
    )
    gaze_penalty = gaze_risk * 100.0 * gaze_weight
    score = base - sit_penalty - eye_penalty - gaze_penalty
    return max(0, min(100, round(score)))
