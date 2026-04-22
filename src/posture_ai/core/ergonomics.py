from __future__ import annotations

import math
import time
from collections import deque
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


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


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


def compute_fatigue_score(
    *,
    posture_score: float | None,
    continuous_sit_seconds: float,
    continuous_gaze_seconds: float,
    face_distance: float | None,
    posture_trend_risk: float = 0.0,
    movement_risk: float = 0.0,
    head_drop_risk: float = 0.0,
    posture_stability_risk: float = 0.0,
    spine_score: float | None = None,
    shoulder_elevation_risk: float = 0.0,
) -> int:
    """Charchoq riskini 0..100 oraliqda baholaydi.

    Bu emotsiyani yuzdan taxmin qilish emas. Kamera orqali ko'rinadigan
    ergonomik signallar: uzluksiz o'tirish, ekranga tikilish, ekran masofasi
    va postura yomonlashuvi asosida risk hisoblanadi.
    """
    sit_risk = sit_duration_risk(
        continuous_sit_seconds,
        comfort_max_seconds=25 * 60.0,
        danger_min_seconds=90 * 60.0,
    )
    gaze_risk = sit_duration_risk(
        continuous_gaze_seconds,
        comfort_max_seconds=20 * 60.0,
        danger_min_seconds=75 * 60.0,
    )
    eye_risk = eye_strain_risk(face_distance) if face_distance is not None else 0.0
    posture_risk = 0.0
    if posture_score is not None:
        posture_risk = max(0.0, min(1.0, (75.0 - float(posture_score)) / 75.0))

    score = (
        (sit_risk * 35.0)
        + (gaze_risk * 25.0)
        + (posture_risk * 25.0)
        + (eye_risk * 15.0)
    )
    spine_risk = 0.0
    if spine_score is not None:
        spine_risk = _clamp01((70.0 - float(spine_score)) / 70.0)

    dynamic_penalty = (
        (_clamp01(posture_trend_risk) * 10.0)
        + (_clamp01(movement_risk) * 8.0)
        + (_clamp01(head_drop_risk) * 8.0)
        + (_clamp01(posture_stability_risk) * 5.0)
        + (spine_risk * 6.0)
        + (_clamp01(shoulder_elevation_risk) * 3.0)
    )
    score += dynamic_penalty
    return max(0, min(100, round(score)))


def fatigue_level(score: int | float) -> str:
    """Risk darajasini matnli kategoriya sifatida qaytaradi."""
    value = float(score)
    if value >= 65.0:
        return "high"
    if value >= 35.0:
        return "moderate"
    return "low"


def fatigue_advice(
    *,
    fatigue_score: int,
    continuous_sit_seconds: float,
    continuous_gaze_seconds: float,
    face_distance: float | None,
) -> str:
    """Charchoq riskiga qarab qisqa maslahat beradi."""
    level = fatigue_level(fatigue_score)
    if level == "high":
        return "Charchoq belgilari ko'rinyapti. 2-5 daqiqa tanaffus qiling, turing va yelkangizni yozing."
    if continuous_gaze_seconds >= 20 * 60:
        return "Ko'z charchashi oshmoqda. 20 soniya uzoqqa qarang va ko'zlaringizni dam oldiring."
    if continuous_sit_seconds >= 25 * 60:
        return "Uzoq o'tirib qoldingiz. Qisqa tanaffus qilib, yengil cho'ziling."
    if face_distance is not None and eye_strain_risk(face_distance) >= 0.75:
        return "Ekranga yaqin o'tiryapsiz. Biroz uzoqlashing va ko'zingizni dam oldiring."
    if level == "moderate":
        return "Charchoq riski oshmoqda. 1-2 daqiqa tanaffus qilish foydali."
    return "Charchoq riski past."


@dataclass(slots=True)
class FatigueAlertTracker:
    """Charchoq alertlarini threshold va cooldown bilan cheklaydi."""

    threshold: int = 65
    cooldown_sec: float = 10 * 60.0
    time_fn: Callable[[], float] = time.monotonic
    last_alert_at: float = field(default=float("-inf"), init=False)

    def needs_fatigue_alert(self, fatigue_score: int | float) -> bool:
        if float(fatigue_score) < self.threshold:
            return False
        now = self.time_fn()
        if (now - self.last_alert_at) < self.cooldown_sec:
            return False
        self.last_alert_at = now
        return True


@dataclass(slots=True)
class FatigueSignalState:
    posture_trend_risk: float = 0.0
    movement_risk: float = 0.0
    head_drop_risk: float = 0.0
    posture_stability_risk: float = 0.0
    spine_score: int | None = None
    shoulder_elevation_risk: float = 0.0
    posture_slope_per_minute: float = 0.0
    micro_movement_rate: float = 0.0

    def as_factors(self) -> dict[str, float]:
        factors = {
            "posture_trend": self.posture_trend_risk,
            "low_movement": self.movement_risk,
            "head_drop": self.head_drop_risk,
            "posture_instability": self.posture_stability_risk,
            "spine_alignment": _clamp01((70.0 - float(self.spine_score or 70)) / 70.0),
            "shoulder_elevation": self.shoulder_elevation_risk,
        }
        return {key: round(value, 3) for key, value in factors.items()}


@dataclass(slots=True)
class FatigueSignalTracker:
    """Sessiya ichidagi dinamik charchoq signallarini kuzatadi."""

    time_fn: Callable[[], float] = time.monotonic
    trend_window_sec: float = 15 * 60.0
    movement_window_sec: float = 2 * 60.0
    stability_window_sec: float = 5 * 60.0
    motion_threshold: float = 5.0
    posture_samples: deque[tuple[float, float]] = field(default_factory=deque, init=False)
    head_samples: deque[tuple[float, float]] = field(default_factory=deque, init=False)
    movement_events: deque[float] = field(default_factory=deque, init=False)
    head_drop_events: deque[float] = field(default_factory=deque, init=False)
    last_head_angle: float | None = field(default=None, init=False)

    def _trim(self, now: float) -> None:
        while self.posture_samples and (now - self.posture_samples[0][0]) > self.trend_window_sec:
            self.posture_samples.popleft()
        while self.head_samples and (now - self.head_samples[0][0]) > self.stability_window_sec:
            self.head_samples.popleft()
        while self.movement_events and (now - self.movement_events[0]) > self.movement_window_sec:
            self.movement_events.popleft()
        while self.head_drop_events and (now - self.head_drop_events[0]) > self.stability_window_sec:
            self.head_drop_events.popleft()

    @staticmethod
    def _linear_slope_per_minute(samples: Sequence[tuple[float, float]]) -> float:
        if len(samples) < 3:
            return 0.0
        first_t = samples[0][0]
        xs = [(t - first_t) / 60.0 for t, _value in samples]
        ys = [value for _t, value in samples]
        mean_x = sum(xs) / len(xs)
        mean_y = sum(ys) / len(ys)
        denominator = sum((x - mean_x) ** 2 for x in xs)
        if denominator <= 1e-9:
            return 0.0
        numerator = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
        return numerator / denominator

    @staticmethod
    def _score_stddev(values: Sequence[float]) -> float:
        if len(values) < 3:
            return 0.0
        mean = sum(values) / len(values)
        variance = sum((value - mean) ** 2 for value in values) / len(values)
        return math.sqrt(variance)

    def observe(
        self,
        *,
        posture_score: float | None,
        head_angle: float | None,
        spine_score: int | None,
        shoulder_elevation: float | None,
        motion_level: float | None = None,
    ) -> FatigueSignalState:
        now = self.time_fn()
        if posture_score is not None:
            self.posture_samples.append((now, float(posture_score)))
        if head_angle is not None:
            self.head_samples.append((now, float(head_angle)))
            if self.last_head_angle is not None and head_angle >= 35.0 and (head_angle - self.last_head_angle) >= 8.0:
                self.head_drop_events.append(now)
            self.last_head_angle = float(head_angle)
        if motion_level is not None and motion_level >= self.motion_threshold:
            self.movement_events.append(now)

        self._trim(now)

        slope = self._linear_slope_per_minute(tuple(self.posture_samples))
        posture_trend_risk = _clamp01((-slope - 0.4) / 2.6)

        movement_rate = 0.0
        movement_risk = 0.0
        if motion_level is not None and self.movement_window_sec > 0:
            movement_rate = len(self.movement_events) / (self.movement_window_sec / 60.0)
            movement_risk = _clamp01((4.0 - movement_rate) / 4.0)

        head_drop_risk = 0.0
        if self.head_samples:
            recent_angles = [angle for _t, angle in self.head_samples]
            high_angles = sum(1 for angle in recent_angles if angle >= 35.0)
            head_drop_risk = _clamp01(high_angles / max(len(recent_angles), 1))
            head_drop_risk = max(head_drop_risk, _clamp01(len(self.head_drop_events) / 3.0))
            if recent_angles[-1] >= 42.0:
                head_drop_risk = max(head_drop_risk, 0.75)

        posture_values = [value for _t, value in self.posture_samples if (now - _t) <= self.stability_window_sec]
        stddev = self._score_stddev(posture_values)
        posture_stability_risk = _clamp01((stddev - 8.0) / 12.0)

        return FatigueSignalState(
            posture_trend_risk=posture_trend_risk,
            movement_risk=movement_risk,
            head_drop_risk=head_drop_risk,
            posture_stability_risk=posture_stability_risk,
            spine_score=spine_score,
            shoulder_elevation_risk=_clamp01(shoulder_elevation or 0.0),
            posture_slope_per_minute=round(slope, 3),
            micro_movement_rate=round(movement_rate, 2),
        )


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
