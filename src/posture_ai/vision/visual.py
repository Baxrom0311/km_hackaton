"""Jonli visual rejim — kamera oynasini ochadi va overlay ko'rsatadi.

Bu rejim asosan:
  - sinov / debug uchun (foydalanuvchi tizim ko'rayotganini ko'radi)
  - hakaton demo videosi uchun (hakamlar landmark va scorelarni ko'radi)

macOS'da cv2.imshow MAIN thread'da chaqirilishi shart, shuning uchun bu rejim
threading ishlatmaydi — barcha logika bir loop ichida.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from posture_ai.vision.detector import REQUIRED_LANDMARKS, PoseDetector, PostureResult, analyze_posture
from posture_ai.os_utils.dimmer import ScreenDimmer
from posture_ai.core.ergonomics import (
    EyeGazeTracker,
    FatigueSignalTracker,
    SitDurationTracker,
    compute_ergonomic_score,
    compute_fatigue_score,
    fatigue_advice,
    fatigue_level,
)
from posture_ai.core.filter import TemporalFilter
from posture_ai.os_utils.notifier import send_notification

logger = logging.getLogger(__name__)

# BlazePose 33 landmark uchun asosiy skelet ulanishlari (chiziqlar)
_POSE_CONNECTIONS = (
    (11, 12), (11, 13), (13, 15), (12, 14), (14, 16),  # qo'llar
    (11, 23), (12, 24), (23, 24),                       # tana
    (23, 25), (25, 27), (24, 26), (26, 28),             # oyoqlar
    (0, 7), (0, 8), (7, 8),                             # bosh
)


@dataclass(slots=True)
class VisualControls:
    show_landmarks: bool = True
    show_info: bool = True
    show_help: bool = True
    notifications_enabled: bool = True
    paused: bool = False
    fullscreen: bool = False
    screenshot_requested: bool = False


def _draw_landmarks(cv2: Any, frame: Any, landmarks: Any) -> None:
    height, width = frame.shape[:2]
    points: list[tuple[int, int]] = []
    for landmark in landmarks:
        x = int(landmark.x * width)
        y = int(landmark.y * height)
        points.append((x, y))

    for a_idx, b_idx in _POSE_CONNECTIONS:
        if a_idx < len(points) and b_idx < len(points):
            cv2.line(frame, points[a_idx], points[b_idx], (200, 200, 200), 2)

    for x, y in points:
        cv2.circle(frame, (x, y), 4, (0, 255, 200), -1)


def _draw_help_overlay(cv2: Any, frame: Any, controls: VisualControls) -> None:
    if not controls.show_help:
        return

    height, width = frame.shape[:2]
    overlay = frame.copy()
    left = max(0, width - 340)
    top = 0

    lines = [
        f"D  debug lines:  {'ON' if controls.show_landmarks else 'OFF'}",
        f"I  info panel:   {'ON' if controls.show_info else 'OFF'}",
        f"N  notifications:{'ON' if controls.notifications_enabled else 'OFF'}",
        f"SPACE  pause:    {'PAUSED' if controls.paused else 'LIVE'}",
        "S  screenshot    F  fullscreen",
        "H  hide help     Q / ESC exit",
    ]
    bottom = min(height, 18 + len(lines) * 22)
    cv2.rectangle(overlay, (left, top), (width, bottom), (0, 0, 0), -1)
    cv2.addWeighted(overlay, 0.45, frame, 0.55, 0, frame)
    for idx, line in enumerate(lines):
        cv2.putText(
            frame,
            line,
            (left + 12, 24 + idx * 22),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.50,
            (230, 230, 230),
            1,
            cv2.LINE_AA,
        )


def _draw_overlay(cv2: Any, frame: Any, result: PostureResult, fps: float, controls: VisualControls, gaze_seconds: float = 0.0) -> None:
    height, width = frame.shape[:2]
    status = result.status
    color = (40, 180, 60) if status == "good" else (40, 40, 220) if status == "bad" else (160, 160, 160)

    # Status border
    cv2.rectangle(frame, (0, 0), (width - 1, height - 1), color, 6)

    _draw_help_overlay(cv2, frame, controls)

    if not controls.show_info:
        return

    # Top-left info paneli
    panel_height = 365
    overlay = frame.copy()
    cv2.rectangle(overlay, (0, 0), (360, panel_height), (0, 0, 0), -1)
    cv2.addWeighted(overlay, 0.55, frame, 0.45, 0, frame)

    def put(text: str, line: int, scale: float = 0.55, color_text: tuple = (255, 255, 255)) -> None:
        y = 24 + line * 22
        cv2.putText(
            frame,
            text,
            (12, y),
            cv2.FONT_HERSHEY_SIMPLEX,
            scale,
            color_text,
            1,
            cv2.LINE_AA,
        )

    put(f"Status: {status.upper()}", 0, scale=0.65, color_text=color)
    if result.skipped:
        reason_text = result.reason or "unknown"
        put(f"Reason: {reason_text}", 1, scale=0.55, color_text=(80, 200, 255))
    else:
        put(f"Posture score: {result.posture_score if result.posture_score is not None else '-'}", 1)
    put(f"Ergonomic:     {result.ergonomic_score if result.ergonomic_score is not None else '-'}", 2)
    sit_min = result.sit_seconds / 60.0
    put(f"Sit duration:  {sit_min:6.1f} min", 3)
    gaze_min = gaze_seconds / 60.0
    gaze_color = (50, 220, 255) if gaze_min >= 18.0 else (255, 255, 255)
    put(f"Eye gaze:      {gaze_min:6.1f} min", 4, color_text=gaze_color)
    put(f"Head angle:    {result.head_angle if result.head_angle is not None else '-'} deg", 5)
    put(f"Face dist:     {result.face_distance if result.face_distance is not None else '-'}", 6)
    facing_label = "-" if result.facing_camera is None else ("yes" if result.facing_camera else "no")
    put(f"Facing cam:    {facing_label}", 7)
    put(f"XY roll:       {result.roll_xy_deg if result.roll_xy_deg is not None else '-'} deg", 8)
    put(f"XZ yaw:        {result.yaw_xz_deg if result.yaw_xz_deg is not None else '-'} deg", 9)
    put(f"YZ pitch:      {result.pitch_yz_deg if result.pitch_yz_deg is not None else '-'} deg", 10)
    put(f"Cam XY view:   {result.camera_roll_xy_deg if result.camera_roll_xy_deg is not None else '-'} deg", 11)
    put(f"Cam XZ view:   {result.camera_yaw_xz_deg if result.camera_yaw_xz_deg is not None else '-'} deg", 12)
    put(f"Cam YZ view:   {result.camera_pitch_yz_deg if result.camera_pitch_yz_deg is not None else '-'} deg", 13)
    put(f"FPS: {fps:5.1f}", 14, scale=0.5, color_text=(180, 220, 255))

    # Pastdagi issues paneli
    if result.issues:
        text = " | ".join(result.issues[:3])
        cv2.rectangle(frame, (0, height - 40), (width, height), (0, 0, 0), -1)
        cv2.putText(
            frame,
            text,
            (12, height - 14),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (50, 220, 255),
            2,
            cv2.LINE_AA,
        )


def handle_visual_key(key: int, controls: VisualControls) -> bool:
    if key in (27, ord("q")):
        return True
    if key == ord("d"):
        controls.show_landmarks = not controls.show_landmarks
        logger.info("Visual: debug lines %s", "ON" if controls.show_landmarks else "OFF")
    elif key == ord("i"):
        controls.show_info = not controls.show_info
        logger.info("Visual: info panel %s", "ON" if controls.show_info else "OFF")
    elif key == ord("h"):
        controls.show_help = not controls.show_help
        logger.info("Visual: help panel %s", "ON" if controls.show_help else "OFF")
    elif key == ord("n"):
        controls.notifications_enabled = not controls.notifications_enabled
        logger.info("Visual: notifications %s", "ON" if controls.notifications_enabled else "OFF")
    elif key == ord(" "):
        controls.paused = not controls.paused
        logger.info("Visual: %s", "PAUSED" if controls.paused else "RESUMED")
    elif key == ord("s"):
        controls.screenshot_requested = True
    elif key == ord("f"):
        controls.fullscreen = not controls.fullscreen
    return False


def run_visual_loop(
    storage: Any,
    session_id: int,
    config: dict[str, Any],
    *,
    show_landmarks: bool = True,
) -> None:
    """Kamera oynasi bilan jonli sinov rejimi.

    ESC yoki q tugmasi bilan to'xtatiladi. Notification va storage logikasi
    konsol/tray rejimlardagi bilan bir xil — temporal filter + cooldown.
    """

    detector = PoseDetector(config)
    detector.open()
    cv2 = detector.cv2

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

    dimmer = ScreenDimmer(dim_level=float(config.get("dim_level", 0.4)))
    dim_enabled = config.get("dim_on_bad_posture", True)
    gaze_tracker = EyeGazeTracker(
        gaze_alert_seconds=float(config.get("gaze_alert_seconds", 20 * 60.0)),
        break_duration_seconds=float(config.get("gaze_break_seconds", 20.0)),
        cooldown_sec=float(config.get("gaze_alert_cooldown_seconds", 60.0)),
    )
    fatigue_signal_tracker = FatigueSignalTracker()

    fps_target = max(int(config.get("fps", 10)), 1)
    frame_interval = 1.0 / fps_target
    log_interval = float(config.get("stats_log_interval_seconds", 60))
    last_logged_at = 0.0
    last_fps_calc = time.monotonic()
    frame_count = 0
    fps_display = 0.0
    controls = VisualControls(show_landmarks=show_landmarks)

    window_name = "PostureAI — Sinov rejimi (ESC chiqish)"
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(window_name, 1280, 820)

    screenshot_dir = Path("screenshots")
    is_fullscreen = False

    logger.info(
        "Visual rejim ishga tushdi. Chiqish: ESC, Q yoki Ctrl+C. Hotkeylar: D I N H SPACE S F."
    )

    try:
        try:
            last_frame = None
            while True:
                started_at = time.monotonic()

                # Fullscreen toggle
                if controls.fullscreen != is_fullscreen:
                    if controls.fullscreen:
                        cv2.setWindowProperty(window_name, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
                    else:
                        cv2.setWindowProperty(window_name, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_NORMAL)
                    is_fullscreen = controls.fullscreen

                # Pause rejimda oxirgi kadrni ko'rsatib turadi
                if controls.paused:
                    if last_frame is not None:
                        pause_frame = last_frame.copy()
                        cv2.putText(
                            pause_frame, "PAUSED (SPACE to resume)",
                            (pause_frame.shape[1] // 2 - 180, pause_frame.shape[0] // 2),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 200, 255), 2, cv2.LINE_AA,
                        )
                        cv2.imshow(window_name, pause_frame)
                    key = cv2.waitKey(50) & 0xFF
                    if handle_visual_key(key, controls):
                        break
                    continue

                ok, frame = detector.read()
                if not ok:
                    logger.warning("Kameradan kadr olib bo'lmadi")
                    sit_tracker.observe(person_present=False)
                    if handle_visual_key(cv2.waitKey(int(frame_interval * 1000)) & 0xFF, controls):
                        break
                    continue

                frame = cv2.flip(frame, 1)

                landmarks = detector.extract_landmarks(frame)
                if landmarks is None:
                    result = PostureResult(status="unknown", skipped=True, reason="no_pose")
                else:
                    result = analyze_posture(
                        landmarks,
                        head_angle_threshold=float(config["head_angle_threshold"]),
                        shoulder_diff_threshold=float(config["shoulder_diff_threshold"]),
                        forward_lean_threshold=float(config["forward_lean_threshold"]),
                        roll_xy_threshold_deg=float(config.get("roll_xy_threshold_deg", 12.0)),
                        yaw_xz_threshold_deg=float(config.get("yaw_xz_threshold_deg", 18.0)),
                        pitch_yz_threshold_deg=float(config.get("pitch_yz_threshold_deg", 18.0)),
                        min_visibility=float(config.get("min_visibility", 0.5)),
                        baseline_head_angle=config.get("baseline_head_angle"),
                        baseline_shoulder_diff=config.get("baseline_shoulder_diff"),
                        baseline_forward_lean=config.get("baseline_forward_lean"),
                        baseline_roll_xy_deg=config.get("baseline_roll_xy_deg"),
                        baseline_yaw_xz_deg=config.get("baseline_yaw_xz_deg"),
                        baseline_pitch_yz_deg=config.get("baseline_pitch_yz_deg"),
                    )
                    if result.skipped and result.reason == "low_visibility":
                        vis = {idx: round(landmarks[idx].visibility, 2) for idx in REQUIRED_LANDMARKS}
                        logger.debug("low_visibility — landmark visibility: %s", vis)

                person_present = not result.skipped and result.posture_score is not None
                sit_tracker.observe(person_present=person_present)
                gaze_tracker.observe(facing_screen=bool(result.facing_camera) if person_present else False)
                result.sit_seconds = round(sit_tracker.continuous_sit_seconds, 1)
                if result.posture_score is not None:
                    fatigue_signals = fatigue_signal_tracker.observe(
                        posture_score=result.posture_score,
                        head_angle=result.head_angle,
                        spine_score=result.spine_score,
                        shoulder_elevation=result.shoulder_elevation,
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
                        continuous_gaze_seconds=gaze_tracker.continuous_gaze_seconds,
                    )
                    result.fatigue_score = compute_fatigue_score(
                        posture_score=result.posture_score,
                        continuous_sit_seconds=result.sit_seconds,
                        face_distance=result.face_distance,
                        continuous_gaze_seconds=gaze_tracker.continuous_gaze_seconds,
                        posture_trend_risk=fatigue_signals.posture_trend_risk,
                        movement_risk=fatigue_signals.movement_risk,
                        head_drop_risk=fatigue_signals.head_drop_risk,
                        posture_stability_risk=fatigue_signals.posture_stability_risk,
                        spine_score=result.spine_score,
                        shoulder_elevation_risk=result.shoulder_elevation or 0.0,
                    )
                    result.fatigue_level = fatigue_level(result.fatigue_score)
                    result.fatigue_advice = fatigue_advice(
                        fatigue_score=result.fatigue_score,
                        continuous_sit_seconds=result.sit_seconds,
                        continuous_gaze_seconds=gaze_tracker.continuous_gaze_seconds,
                        face_distance=result.face_distance,
                    )

                if landmarks is not None and controls.show_landmarks:
                    _draw_landmarks(cv2, frame, landmarks)
                _draw_overlay(cv2, frame, result, fps_display, controls, gaze_seconds=gaze_tracker.continuous_gaze_seconds)
                cv2.imshow(window_name, frame)
                last_frame = frame

                # Screenshot
                if controls.screenshot_requested:
                    controls.screenshot_requested = False
                    screenshot_dir.mkdir(exist_ok=True)
                    ts = time.strftime("%Y%m%d_%H%M%S")
                    path = screenshot_dir / f"postureai_{ts}.png"
                    cv2.imwrite(str(path), frame)
                    logger.info("Screenshot saqlandi: %s", path)

                if controls.notifications_enabled and not result.skipped and temporal_filter.update(result.status == "bad"):
                    send_notification("PostureAI", issues=result.issues)
                    storage.log_alert(result.issues, timestamp=result.timestamp)
                    logger.info("Posture alert: %s", " | ".join(result.issues))
                    if dim_enabled:
                        dimmer.dim()

                if not result.skipped and result.status == "good" and dimmer.is_dimmed:
                    dimmer.restore()

                if controls.notifications_enabled and sit_tracker.needs_break_alert():
                    send_notification("PostureAI", issues=["Tanaffus qiling!"])
                    storage.log_alert(["Tanaffus qiling!"])
                    logger.info("Break alert: 25+ daqiqa uzluksiz o'tirish")
                    if dim_enabled:
                        dimmer.dim()

                if controls.notifications_enabled and gaze_tracker.needs_gaze_alert():
                    send_notification("PostureAI", issues=["20-20-20!"])
                    storage.log_alert(["20-20-20!"])
                    logger.info("Gaze alert: 20+ daqiqa uzluksiz ekranga qarash")
                    if dim_enabled:
                        dimmer.dim()

                now = time.monotonic()
                if person_present and (last_logged_at == 0.0 or (now - last_logged_at) >= log_interval):
                    storage.log_posture(session_id, result)
                    last_logged_at = now

                frame_count += 1
                if now - last_fps_calc >= 1.0:
                    fps_display = frame_count / (now - last_fps_calc)
                    frame_count = 0
                    last_fps_calc = now

                elapsed = time.monotonic() - started_at
                wait_ms = max(1, int((frame_interval - elapsed) * 1000))
                key = cv2.waitKey(wait_ms) & 0xFF
                if handle_visual_key(key, controls):
                    break
        except KeyboardInterrupt:
            logger.info("Visual rejim Ctrl+C bilan to'xtatildi.")
    finally:
        dimmer.restore()
        detector.close()
        cv2.destroyAllWindows()
