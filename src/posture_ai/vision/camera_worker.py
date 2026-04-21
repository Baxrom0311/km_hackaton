from PySide6.QtCore import QThread, Signal
from loguru import logger
import time
import cv2
import numpy as np
from posture_ai.vision.detector import PoseDetector, PostureResult
from posture_ai.core.filter import TemporalFilter
from posture_ai.core.ergonomics import SitDurationTracker, EyeGazeTracker, compute_ergonomic_score
from posture_ai.core.config import AppConfig


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
    NO_MOTION_SLEEP = 2.0        # harakat yo'q → 2 sek uxlash
    MOTION_CHECK_INTERVAL = 0.5  # motion tekshirish oralig'i
    STATIC_RECHECK_INTERVAL = 1.5

    def __init__(self, config: AppConfig, parent=None):
        super().__init__(parent)
        self.config = config
        self._is_running = True
        self._force_ai_sampling = False
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

    def _handle_result(self, result: PostureResult) -> None:
        person_present = not result.skipped and result.posture_score is not None
        facing_screen = bool(result.facing_camera) if person_present else False

        self.sit_tracker.observe(person_present=person_present)
        self.gaze_tracker.observe(facing_screen=facing_screen)

        result.sit_seconds = round(self.sit_tracker.continuous_sit_seconds, 1)
        if result.posture_score is not None:
            result.ergonomic_score = compute_ergonomic_score(
                result.posture_score,
                continuous_sit_seconds=result.sit_seconds,
                face_distance=result.face_distance,
                continuous_gaze_seconds=self.gaze_tracker.continuous_gaze_seconds,
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

    def stop(self):
        self._is_running = False

    def set_force_ai_sampling(self, enabled: bool) -> None:
        """Kalibrovka kabi holatlarda motion skip'ni vaqtincha o'chiradi."""
        self._force_ai_sampling = enabled

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
        # OS darajasida past prioritet
        try:
            import os
            os.nice(10)
        except (OSError, AttributeError):
            pass

        fps = max(self.config.fps, 1)
        frame_interval = 1.0 / fps
        ai_skip = max(1, getattr(self.config, "ai_skip_frames", 2))
        self._last_result = None

        try:
            self.detector.open()
        except Exception as e:
            logger.exception("Camera could not start.")
            self.camera_error.emit(str(e))
            return

        logger.info(f"CameraWorker bashlandi (fps={fps}, ai_skip={ai_skip}, motion_detect=ON)")

        consecutive_fails = 0
        last_reconnect = time.monotonic()
        frame_count = 0
        prev_gray = None
        last_ai_at = float("-inf")

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
                    else:
                        self.camera_error.emit("Kamera javob bermayapti")
                        break
                time.sleep(frame_interval)
                continue

            consecutive_fails = 0
            frame_count += 1
            frame = cv2.flip(frame, 1)

            # ══════ MOTION DETECTION (arzon — CPU ~0.1%) ══════
            curr_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            # Blur qilish — shovqinni kamaytirish
            curr_gray = cv2.GaussianBlur(curr_gray, (21, 21), 0)
            motion = self._detect_motion(prev_gray, curr_gray)
            prev_gray = curr_gray

            has_motion = motion > self.MOTION_THRESHOLD
            force_ai_sampling = self._force_ai_sampling

            if not has_motion and not force_ai_sampling:
                if (started_at - last_ai_at) >= self.STATIC_RECHECK_INTERVAL:
                    self._handle_result(self.detector.process_frame(frame))
                    last_ai_at = started_at

                # Harakat yo'q → uzoqroq uxlash (CPU tejash)
                self.frame_processed.emit(frame)
                time.sleep(max(frame_interval, self.MOTION_CHECK_INTERVAL))
                continue

            # ══════ HARAKAT BOR YOKI KALIBROVKA — AI ishlaydi ══════
            run_ai = (frame_count % ai_skip == 0)

            if run_ai:
                self._handle_result(self.detector.process_frame(frame))
                last_ai_at = started_at

            # Frame UI ga — hamma kadrni yuboramiz (smooth ko'rinishi uchun)
            self.frame_processed.emit(frame)

            elapsed = time.monotonic() - started_at
            remaining = frame_interval - elapsed
            if remaining > 0:
                time.sleep(remaining)

        self.detector.close()
        logger.info("CameraWorker to'xtadi.")
