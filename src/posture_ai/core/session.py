"""Ergonomik sessiya boshqaruvchisi — signal tracking va alert logika.

camera_worker.py va detector.py dagi umumiy logikani bir joyga to'playdi:
  - SitDurationTracker, EyeGazeTracker, FatigueSignalTracker boshqaruvi
  - PostureResult ni ergonomik metrikalar bilan boyitish
  - Alert holatlarini aniqlash (posture, sit break, gaze, fatigue)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence

from posture_ai.core.ergonomics import (
    EyeGazeTracker,
    FatigueAlertTracker,
    FatigueSignalTracker,
    SitDurationTracker,
    compute_ergonomic_score,
    compute_fatigue_score,
    fatigue_advice,
    fatigue_level,
)
from posture_ai.core.filter import TemporalFilter
from posture_ai.vision.scoring import PostureResult


@dataclass(slots=True)
class AlertEvent:
    """Ogohlantirish voqeasi."""
    result: PostureResult
    alert_type: str  # "posture" | "sit_break" | "gaze" | "fatigue"


@dataclass
class SessionProcessor:
    """CameraWorker va detection loop uchun umumiy sessiya boshqaruvchisi.

    PostureResult ni qabul qiladi, ergonomik metrikalar bilan boyitadi
    va zarur bo'lsa alert voqealarini qaytaradi.
    """

    temporal_filter: TemporalFilter
    sit_tracker: SitDurationTracker
    gaze_tracker: EyeGazeTracker
    fatigue_signal_tracker: FatigueSignalTracker
    fatigue_alert_tracker: FatigueAlertTracker | None = None

    def enrich_result(
        self,
        result: PostureResult,
        *,
        motion_level: float | None = None,
    ) -> None:
        """PostureResult ni ergonomik va charchoq metrikalari bilan boyitadi.

        Bu metod result obyektini in-place o'zgartiradi:
        - sit_seconds, ergonomic_score, fatigue_score va boshqa maydonlarni to'ldiradi
        - sit_tracker va gaze_tracker ni yangilaydi
        """
        person_present = not result.skipped and result.posture_score is not None
        facing_screen = bool(result.facing_camera) if person_present else False

        self.sit_tracker.observe(person_present=person_present)
        self.gaze_tracker.observe(facing_screen=facing_screen)

        result.sit_seconds = round(self.sit_tracker.continuous_sit_seconds, 1)

        if result.posture_score is not None:
            fatigue_signals = self.fatigue_signal_tracker.observe(
                posture_score=result.posture_score,
                head_angle=result.head_angle,
                spine_score=getattr(result, "spine_score", None),
                shoulder_elevation=getattr(result, "shoulder_elevation", None),
                motion_level=motion_level,
            )
            result.posture_trend_risk = fatigue_signals.posture_trend_risk
            result.movement_risk = fatigue_signals.movement_risk
            result.head_drop_risk = fatigue_signals.head_drop_risk
            result.posture_stability_risk = fatigue_signals.posture_stability_risk
            result.fatigue_factors = fatigue_signals.as_factors()

            result.ergonomic_score = compute_ergonomic_score(
                result.posture_score,
                continuous_sit_seconds=result.sit_seconds,
                face_distance=result.face_distance,
                continuous_gaze_seconds=self.gaze_tracker.continuous_gaze_seconds,
            )
            result.fatigue_score = compute_fatigue_score(
                posture_score=result.posture_score,
                continuous_sit_seconds=result.sit_seconds,
                face_distance=result.face_distance,
                continuous_gaze_seconds=self.gaze_tracker.continuous_gaze_seconds,
                posture_trend_risk=fatigue_signals.posture_trend_risk,
                movement_risk=fatigue_signals.movement_risk,
                head_drop_risk=fatigue_signals.head_drop_risk,
                posture_stability_risk=fatigue_signals.posture_stability_risk,
                spine_score=getattr(result, "spine_score", None),
                shoulder_elevation_risk=getattr(result, "shoulder_elevation", 0.0) or 0.0,
            )
            result.fatigue_level = fatigue_level(result.fatigue_score)
            result.fatigue_advice = fatigue_advice(
                fatigue_score=result.fatigue_score,
                continuous_sit_seconds=result.sit_seconds,
                continuous_gaze_seconds=self.gaze_tracker.continuous_gaze_seconds,
                face_distance=result.face_distance,
            )

    def check_alerts(self, result: PostureResult) -> list[AlertEvent]:
        """Ogohlantirish kerakligini tekshiradi va ro'yxatini qaytaradi.

        enrich_result() chaqirilgandan KEYIN chaqirilishi kerak.
        """
        alerts: list[AlertEvent] = []

        # Posture temporal filter
        if not result.skipped and self.temporal_filter.update(result.status == "bad"):
            alerts.append(AlertEvent(result=result, alert_type="posture"))

        # Sit break alert
        if self.sit_tracker.needs_break_alert():
            break_result = PostureResult(
                status="bad",
                issues=["Tanaffus qiling!"],
                sit_seconds=result.sit_seconds,
                ergonomic_score=result.ergonomic_score,
                break_alert=True,
            )
            alerts.append(AlertEvent(result=break_result, alert_type="sit_break"))

        # Gaze alert (20-20-20)
        if self.gaze_tracker.needs_gaze_alert():
            gaze_result = PostureResult(
                status="bad",
                issues=["20-20-20!"],
                sit_seconds=result.sit_seconds,
                ergonomic_score=result.ergonomic_score,
            )
            alerts.append(AlertEvent(result=gaze_result, alert_type="gaze"))

        # Fatigue alert
        if (
            self.fatigue_alert_tracker is not None
            and result.fatigue_score is not None
            and self.fatigue_alert_tracker.needs_fatigue_alert(result.fatigue_score)
        ):
            fatigue_result = PostureResult(
                status="bad",
                issues=["Charchoq belgilari: tanaffus qiling!"],
                sit_seconds=result.sit_seconds,
                ergonomic_score=result.ergonomic_score,
                fatigue_score=result.fatigue_score,
                fatigue_level=result.fatigue_level,
                fatigue_advice=result.fatigue_advice,
                fatigue_alert=True,
            )
            alerts.append(AlertEvent(result=fatigue_result, alert_type="fatigue"))

        return alerts

    def process(
        self,
        result: PostureResult,
        *,
        motion_level: float | None = None,
    ) -> list[AlertEvent]:
        """PostureResult ni boyitadi va alertlarni tekshiradi.

        Bu enrich_result() + check_alerts() ni birgalikda chaqiradi.
        """
        self.enrich_result(result, motion_level=motion_level)
        return self.check_alerts(result)
