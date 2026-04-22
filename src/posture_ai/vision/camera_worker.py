from PySide6.QtCore import QThread, Signal
from loguru import logger
import time
import cv2
import numpy as np
from posture_ai.vision.detector import PoseDetector, PostureResult
from posture_ai.core.filter import TemporalFilter
from posture_ai.core.ergonomics import (
    FatigueAlertTracker,
    FatigueSignalTracker,
    SitDurationTracker,
    EyeGazeTracker,
    compute_ergonomic_score,
    compute_fatigue_score,
    fatigue_advice,
    fatigue_level,
)
from posture_ai.core.config import AppConfig


_POSE_CONNECTIONS = (
    (11, 12), (11, 13), (13, 15), (12, 14), (14, 16),
    (11, 23), (12, 24), (23, 24),
    (23, 25), (25, 27), (24, 26), (26, 28),
    (0, 7), (0, 8), (7, 8),
)


class CameraWorker(QThread):
    """Kamera bilan ishlaydigan background thread.

    Resurs tejash strategiyasi (antivirus/Tailscale pattern):
      1. Motion detection — harakat yo'q bo'lsa AI chaqirilmaydi
      2. Adaptive FPS — harakat yo'q → sekin, harakat bor → tez
      3. AI skip frames — har kadrda emas, faqat har N-chisida
      4. Past OS priority — boshqa dasturlarga xalaqit bermaydi
      5. Periodic reconnect — kamera hang bo'lsa avtomatik tiklash
    """

    frame_processed = Signal(object)
    metrics_updated = Signal(object)
    alert_triggered = Signal(object)
    camera_error = Signal(str)

    RECONNECT_INTERVAL = 30 * 60
    MAX_CONSECUTIVE_FAILS = 50
    MAX_RECONNECT_ATTEMPTS = 5

    # Motion detection parametrlari
    MOTION_THRESHOLD = 5.0       # pixel farq threshold
    STATIC_RECHECK_INTERVAL = 1.5
    SLOW_AI_LOG_INTERVAL = 5.0
    OVERLAY_STALE_SECONDS = 2.5
    LIVE_PREVIEW_MAX_AI_FPS = 10.0

    def __init__(self, config: AppConfig, parent=None):
        super().__init__(parent)
        self.config = config
        self._is_running = True
        self._force_ai_sampling = False
        self._live_preview_mode = True
        self.detector = PoseDetector(config.model_dump())

        self.temporal_filter = TemporalFilter(
            window_size=config.temporal_window_size,
            threshold=config.temporal_threshold,
            cooldown_sec=config.cooldown_seconds,
        )
        self.sit_tracker = SitDurationTracker(
            break_threshold_sec=config.sit_break_threshold_seconds,
            alert_threshold_sec=config.sit_alert_threshold_seconds,
            cooldown_sec=config.sit_alert_cooldown_seconds,
        )
        self.gaze_tracker = EyeGazeTracker(
            gaze_alert_seconds=20 * 60, break_duration_seconds=20, cooldown_sec=60
        )
        self.fatigue_tracker = FatigueAlertTracker(
            threshold=config.fatigue_alert_threshold,
            cooldown_sec=config.fatigue_alert_cooldown_seconds,
        )
        self.fatigue_signal_tracker = FatigueSignalTracker()
        self._last_result: PostureResult | None = None
        self._last_landmarks = None
        self._last_landmarks_at = float("-inf")

    def _handle_result(self, result: PostureResult, motion_level: float | None = None) -> None:
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

        self._last_result = result
        self.metrics_updated.emit(result)

        if not result.skipped and self.temporal_filter.update(result.status == "bad"):
            self.alert_triggered.emit(result)

        if self.sit_tracker.needs_break_alert():
            self.alert_triggered.emit(
                PostureResult(
                    status="bad",
                    issues=["Tanaffus qiling!"],
                    sit_seconds=result.sit_seconds,
                    ergonomic_score=result.ergonomic_score,
                    break_alert=True,
                )
            )

        if self.gaze_tracker.needs_gaze_alert():
            self.alert_triggered.emit(
                PostureResult(
                    status="bad",
                    issues=["20-20-20!"],
                    sit_seconds=result.sit_seconds,
                    ergonomic_score=result.ergonomic_score,
                )
            )

        if result.fatigue_score is not None and self.fatigue_tracker.needs_fatigue_alert(result.fatigue_score):
            self.alert_triggered.emit(
                PostureResult(
                    status="bad",
                    issues=["Charchoq belgilari: tanaffus qiling!"],
                    sit_seconds=result.sit_seconds,
                    ergonomic_score=result.ergonomic_score,
                    fatigue_score=result.fatigue_score,
                    fatigue_level=result.fatigue_level,
                    fatigue_advice=result.fatigue_advice,
                    fatigue_alert=True,
                )
            )

    @staticmethod
    def _draw_landmark_overlay(frame, landmarks, result: PostureResult):
        overlay = frame.copy()
        height, width = overlay.shape[:2]
        border_color = (45, 220, 170) if result.status == "good" else (64, 64, 230)
        if result.skipped:
            border_color = (180, 180, 180)

        if landmarks is not None:
            points: list[tuple[int, int]] = []
            visible: list[bool] = []
            for landmark in landmarks:
                x = int(landmark.x * width)
                y = int(landmark.y * height)
                points.append((x, y))
                visible.append(getattr(landmark, "visibility", 1.0) >= 0.35)

            for a_idx, b_idx in _POSE_CONNECTIONS:
                if a_idx < len(points) and b_idx < len(points) and visible[a_idx] and visible[b_idx]:
                    cv2.line(overlay, points[a_idx], points[b_idx], (190, 190, 210), 2, cv2.LINE_AA)

            for idx, (x, y) in enumerate(points):
                if idx < len(visible) and visible[idx]:
                    cv2.circle(overlay, (x, y), 4, (0, 245, 212), -1, cv2.LINE_AA)
                    cv2.circle(overlay, (x, y), 7, (0, 245, 212), 1, cv2.LINE_AA)

        cv2.rectangle(overlay, (0, 0), (width - 1, height - 1), border_color, 5)
        score = result.ergonomic_score if result.ergonomic_score is not None else result.posture_score
        status_text = result.status.upper() if not result.skipped else (result.reason or "SEARCHING").upper()
        label = f"{status_text} | score {score if score is not None else '--'}"
        cv2.rectangle(overlay, (0, 0), (min(width, 360), 42), (5, 7, 14), -1)
        cv2.putText(
            overlay,
            label,
            (14, 28),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.72,
            border_color,
            2,
            cv2.LINE_AA,
        )
        return overlay

    def _process_ai_frame(self, frame, motion_level: float | None):
        landmarks = self.detector.extract_landmarks(frame)
        if landmarks is None:
            result = PostureResult(status="unknown", skipped=True, reason="no_pose")
        else:
            result = self.detector.analyze_landmarks(landmarks)

        self._handle_result(result, motion_level=motion_level)
        self._last_landmarks = landmarks
        self._last_landmarks_at = time.monotonic()
        return self._draw_landmark_overlay(frame, landmarks, result)

    def _compose_preview_frame(self, frame, now: float):
        if self._last_result is None:
            return frame.copy()
        if (now - self._last_landmarks_at) > self.OVERLAY_STALE_SECONDS:
            return frame.copy()
        return self._draw_landmark_overlay(frame, self._last_landmarks, self._last_result)

    def stop(self):
        self._is_running = False

    def set_force_ai_sampling(self, enabled: bool) -> None:
        """Kalibrovka kabi holatlarda motion skip'ni vaqtincha o'chiradi."""
        self._force_ai_sampling = enabled

    def set_live_preview_mode(self, enabled: bool) -> None:
        """Kamera sahifasi ochiq bo'lsa landmarklarni tezroq yangilash."""
        self._live_preview_mode = enabled

    def _reconnect_camera(self) -> bool:
        logger.info("Kamera qayta ulanmoqda...")
        try:
            self.detector.close()
        except Exception:
            pass
        for attempt in range(1, self.MAX_RECONNECT_ATTEMPTS + 1):
            if not self._is_running:
                return False
            try:
                self.detector = PoseDetector(self.config.model_dump())
                self.detector.open()
                logger.info(f"Kamera qayta ulandi (urinish {attempt})")
                return True
            except Exception as e:
                logger.warning(f"Reconnect {attempt}/{self.MAX_RECONNECT_ATTEMPTS}: {e}")
                time.sleep(2)
        return False

    @staticmethod
    def _detect_motion(prev_gray, curr_gray) -> float:
        """Ikki kadr orasidagi harakat miqdorini aniqlash (arzon operatsiya).

        Bu AI'dan 100x arzon — faqat pixel farqni tekshiradi.
        Return: o'rtacha pixel farq (0=harakat yo'q, 255=butunlay o'zgardi)
        """
        if prev_gray is None:
            return 999.0  # birinchi kadr — har doim "harakat bor"
        diff = cv2.absdiff(prev_gray, curr_gray)
        return float(np.mean(diff))

    def run(self):
        fps = max(self.config.fps, 1)
        frame_interval = 1.0 / fps
        ai_skip = max(1, getattr(self.config, "ai_skip_frames", 2))
        preview_fps = max(1, min(getattr(self.config, "preview_fps", 15), fps))
        preview_interval = 1.0 / preview_fps
        base_ai_interval = max(ai_skip / fps, 0.25)
        live_preview_ai_interval = min(
            base_ai_interval,
            1.0 / min(preview_fps, self.LIVE_PREVIEW_MAX_AI_FPS),
        )
        self._last_result = None
        self._last_landmarks = None
        self._last_landmarks_at = float("-inf")

        try:
            self.detector.open()
        except Exception as e:
            logger.exception("Camera could not start.")
            self.camera_error.emit(str(e))
            return

        logger.info(
            "CameraWorker bashlandi "
            f"(fps={fps}, preview_fps={preview_fps}, "
            f"ai_interval={base_ai_interval:.2f}s, live_ai_interval={live_preview_ai_interval:.2f}s, "
            "motion_detect=ON)"
        )

        consecutive_fails = 0
        last_reconnect = time.monotonic()
        prev_gray = None
        last_ai_at = float("-inf")
        last_preview_emit_at = float("-inf")
        last_slow_ai_log_at = 0.0

        while self._is_running:
            started_at = time.monotonic()

            # Periodic reconnect
            if (started_at - last_reconnect) >= self.RECONNECT_INTERVAL:
                if self._reconnect_camera():
                    last_reconnect = time.monotonic()
                    consecutive_fails = 0
                    prev_gray = None
                else:
                    self.camera_error.emit("Kamerani qayta ulab bo'lmadi")
                    break

            ok, frame = self.detector.read()
            if not ok:
                consecutive_fails += 1
                self.sit_tracker.observe(person_present=False)
                if consecutive_fails >= self.MAX_CONSECUTIVE_FAILS:
                    logger.warning(f"{consecutive_fails} ta ketma-ket xato, reconnect...")
                    if self._reconnect_camera():
                        consecutive_fails = 0
                        last_reconnect = time.monotonic()
                        prev_gray = None
                        self._last_landmarks = None
                        self._last_landmarks_at = float("-inf")
                    else:
                        self.camera_error.emit("Kamera javob bermayapti")
                        break
                time.sleep(frame_interval)
                continue

            consecutive_fails = 0
            frame = cv2.flip(frame, 1)

            now = time.monotonic()

            # ══════ MOTION DETECTION (arzon — CPU ~0.1%) ══════
            curr_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            # Blur qilish — shovqinni kamaytirish
            curr_gray = cv2.GaussianBlur(curr_gray, (21, 21), 0)
            motion = self._detect_motion(prev_gray, curr_gray)
            prev_gray = curr_gray

            has_motion = motion > self.MOTION_THRESHOLD
            force_ai_sampling = self._force_ai_sampling
            active_ai_interval = live_preview_ai_interval if self._live_preview_mode else base_ai_interval

            if not has_motion and not force_ai_sampling:
                if (started_at - last_ai_at) >= self.STATIC_RECHECK_INTERVAL:
                    ai_started_at = time.monotonic()
                    overlay_frame = self._process_ai_frame(frame, motion_level=motion)
                    last_ai_at = time.monotonic()
                    self.frame_processed.emit(overlay_frame)
                    last_preview_emit_at = last_ai_at
                    ai_elapsed = last_ai_at - ai_started_at
                    if ai_elapsed > active_ai_interval and (last_ai_at - last_slow_ai_log_at) >= self.SLOW_AI_LOG_INTERVAL:
                        logger.debug(f"AI inferensiya sekin: {ai_elapsed:.2f}s")
                        last_slow_ai_log_at = last_ai_at
                elif (started_at - last_preview_emit_at) >= preview_interval:
                    self.frame_processed.emit(self._compose_preview_frame(frame, started_at))
                    last_preview_emit_at = started_at

                elapsed = time.monotonic() - started_at
                remaining = frame_interval - elapsed
                if remaining > 0:
                    time.sleep(remaining)
                continue

            # ══════ HARAKAT BOR YOKI KALIBROVKA — AI ishlaydi ══════
            run_ai = (started_at - last_ai_at) >= active_ai_interval

            if run_ai:
                ai_started_at = time.monotonic()
                overlay_frame = self._process_ai_frame(frame, motion_level=motion)
                last_ai_at = time.monotonic()
                self.frame_processed.emit(overlay_frame)
                last_preview_emit_at = last_ai_at
                ai_elapsed = last_ai_at - ai_started_at
                if ai_elapsed > active_ai_interval and (last_ai_at - last_slow_ai_log_at) >= self.SLOW_AI_LOG_INTERVAL:
                    logger.debug(f"AI inferensiya sekin: {ai_elapsed:.2f}s")
                    last_slow_ai_log_at = last_ai_at
            elif (started_at - last_preview_emit_at) >= preview_interval:
                self.frame_processed.emit(self._compose_preview_frame(frame, started_at))
                last_preview_emit_at = started_at

            elapsed = time.monotonic() - started_at
            remaining = frame_interval - elapsed
            if remaining > 0:
                time.sleep(remaining)

        self.detector.close()
        logger.info("CameraWorker to'xtadi.")
