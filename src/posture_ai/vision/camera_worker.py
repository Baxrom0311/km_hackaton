from PySide6.QtCore import QThread, Signal
from loguru import logger
import time
from posture_ai.vision.detector import PoseDetector, PostureResult
from posture_ai.core.filter import TemporalFilter
from posture_ai.core.ergonomics import SitDurationTracker, EyeGazeTracker, compute_ergonomic_score
from posture_ai.core.config import AppConfig

class CameraWorker(QThread):
    # Signals to communicate securely with the main GUI thread
    frame_processed = Signal(object) # raw frame for display
    metrics_updated = Signal(object) # PostureResult object
    alert_triggered = Signal(object) # Specifically important alerts (PosturResult)

    def __init__(self, config: AppConfig, parent=None):
        super().__init__(parent)
        self.config = config
        self._is_running = True
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

    def stop(self):
        self._is_running = False
        self.wait()

    def run(self):
        fps = max(self.config.fps, 1)
        frame_interval = 1.0 / fps
        
        try:
            self.detector.open()
        except Exception as e:
            logger.exception("Camera could not start.")
            return

        logger.info("CameraWorker bashlandi.")
        while self._is_running:
            started_at = time.monotonic()
            ok, frame = self.detector.read()
            if not ok:
                self.sit_tracker.observe(person_present=False)
                time.sleep(frame_interval)
                continue

            # Process AI model
            result = self.detector.process_frame(frame)
            person_present = not result.skipped and result.posture_score is not None
            
            self.sit_tracker.observe(person_present=person_present)
            self.gaze_tracker.observe(facing_screen=person_present)

            result.sit_seconds = round(self.sit_tracker.continuous_sit_seconds, 1)
            if result.posture_score is not None:
                result.ergonomic_score = compute_ergonomic_score(
                    result.posture_score,
                    continuous_sit_seconds=result.sit_seconds,
                    face_distance=result.face_distance,
                    continuous_gaze_seconds=self.gaze_tracker.continuous_gaze_seconds,
                )

            # Emit normal updates for dashboard
            self.metrics_updated.emit(result)

            # Alerts
            if not result.skipped and self.temporal_filter.update(result.status == "bad"):
                self.alert_triggered.emit(result)

            if self.sit_tracker.needs_break_alert():
                break_result = PostureResult(
                    status="bad", issues=["Tanaffus qiling!"], 
                    sit_seconds=result.sit_seconds, ergonomic_score=result.ergonomic_score, break_alert=True
                )
                self.alert_triggered.emit(break_result)

            if self.gaze_tracker.needs_gaze_alert():
                gaze_result = PostureResult(
                    status="bad", issues=["20-20-20!"], sit_seconds=result.sit_seconds, ergonomic_score=result.ergonomic_score
                )
                self.alert_triggered.emit(gaze_result)

            # Emit frame roughly converted to RGB for PySide6 rendering (this is optional but good for UI)
            # Actually we'll keep it raw and let UI convert it
            self.frame_processed.emit(frame)

            elapsed = time.monotonic() - started_at
            remaining = frame_interval - elapsed
            if remaining > 0:
                time.sleep(remaining)

        self.detector.close()
        logger.info("CameraWorker to'xtadi.")
