from __future__ import annotations

import argparse
import json
import logging
import queue
import subprocess
import sys
import threading
from pathlib import Path
from typing import Any

from detector import check_runtime_dependencies, collect_calibration_profile, run_detection_loop
from forecast import forecast_risk
from storage import Storage
from tray import run_app, run_console_app

DEFAULT_CONFIG: dict[str, Any] = {
    "head_angle_threshold": 25.0,
    "shoulder_diff_threshold": 0.07,
    "forward_lean_threshold": -0.2,
    "temporal_window_size": 90,
    "temporal_threshold": 0.7,
    "cooldown_seconds": 60,
    "camera_index": 0,
    "fps": 10,
    "language": "uz",
    "min_visibility": 0.5,
    "model_complexity": 2,
    "min_detection_confidence": 0.5,
    "min_pose_presence_confidence": 0.5,
    "min_tracking_confidence": 0.5,
    "stats_log_interval_seconds": 60,
    "calibration_seconds": 12,
    "calibration_min_samples": 25,
    "baseline_head_angle": None,
    "baseline_shoulder_diff": None,
    "baseline_forward_lean": None,
    "model_asset_path": "models/pose_landmarker_heavy.task",
    "sit_break_threshold_seconds": 60,
    "sit_alert_threshold_seconds": 1500,
    "sit_alert_cooldown_seconds": 300,
}


def load_config(path: str) -> dict[str, Any]:
    config = dict(DEFAULT_CONFIG)
    config_path = Path(path)
    if not config_path.exists():
        return config
    with config_path.open("r", encoding="utf-8") as handle:
        config.update(json.load(handle))
    return config


def save_config(path: str, config: dict[str, Any]) -> None:
    config_path = Path(path)
    config_path.parent.mkdir(parents=True, exist_ok=True)
    with config_path.open("w", encoding="utf-8") as handle:
        json.dump(config, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )


def validate_environment() -> None:
    missing = check_runtime_dependencies()
    if not missing:
        return

    modules = ", ".join(missing)
    raise RuntimeError(
        f"Quyidagi paketlar topilmadi: {modules}. `pip install -r requirements.txt` ni ishlating. "
        "MediaPipe uchun Python 3.11 tavsiya etiladi."
    )


def run_doctor(config: dict[str, Any], db_path: str) -> int:
    print("PostureAI Doctor")
    print(f"- Config: ok ({config.get('camera_index')=}, {config.get('fps')=})")

    storage = Storage(db_path)
    storage.initialize()
    print(f"- SQLite: ok ({db_path})")

    missing = check_runtime_dependencies()
    if missing:
        print(f"- Dependencies: missing ({', '.join(missing)})")
        return 1

    print("- Dependencies: ok")
    model_path = Path(str(config.get("model_asset_path", ""))).expanduser()
    if not model_path.exists():
        print(f"- Model: fail ({model_path})")
        return 1
    print(f"- Model: ok ({model_path})")
    camera_check = (
        "import cv2, sys; "
        f"capture = cv2.VideoCapture({int(config['camera_index'])}); "
        "opened = capture.isOpened(); "
        "ok = False; "
        "frame = None; "
        "ok, frame = capture.read() if opened else (False, None); "
        "capture.release(); "
        "sys.exit(0 if opened and ok else 2)"
    )
    try:
        result = subprocess.run(
            [sys.executable, "-c", camera_check],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=8,
            check=False,
        )
    except subprocess.TimeoutExpired:
        print(f"- Camera: fail (timeout, index={config['camera_index']})")
        return 1

    if result.returncode != 0:
        print(f"- Camera: fail (index={config['camera_index']})")
        return 1

    print(f"- Camera: ok (index={config['camera_index']})")

    return 0


def render_stats_report(config: dict[str, Any], db_path: str) -> str:
    storage = Storage(db_path)
    storage.initialize()
    today = storage.get_today_stats()
    weekly = storage.get_weekly_summary()

    max_sit_min = float(today.get("max_sit_seconds", 0.0)) / 60.0
    lines = [
        "PostureAI Stats",
        f"- Today: good={today['good_pct']:.1f}% bad={today['bad_pct']:.1f}% avg_score={today['avg_score']:.1f}",
        f"- Ergonomic: avg={today.get('avg_ergonomic', 0.0):.1f} | longest_sit={max_sit_min:.1f} min",
        f"- Samples: {today['total_samples']} | Alerts: {today['alerts_count']}",
    ]

    calibration_ready = all(
        config.get(key) is not None
        for key in ("baseline_head_angle", "baseline_shoulder_diff", "baseline_forward_lean")
    )
    if calibration_ready:
        lines.append(
            "- Calibration:"
            f" head={config['baseline_head_angle']},"
            f" shoulder={config['baseline_shoulder_diff']},"
            f" lean={config['baseline_forward_lean']}"
        )
    else:
        lines.append("- Calibration: not set")

    if weekly:
        lines.append("- Weekly:")
        for row in weekly:
            lines.append(
                f"  {row['day']} | good={row['good_pct']:.1f}% | posture={row['avg_score']:.1f} "
                f"| ergo={row.get('avg_ergonomic', 0.0):.1f} | bad={row['bad_count']}"
            )
    else:
        lines.append("- Weekly: no data")

    forecast = forecast_risk(weekly)
    if forecast is not None:
        lines.append("- Forecast:")
        lines.append(
            f"  current_risk={forecast.current_risk:.1f} ({forecast.category}) "
            f"| 7d_projected={forecast.projected_risk_7d:.1f} "
            f"| slope/day={forecast.slope_per_day:+.2f}"
        )
        lines.append(
            f"  30 kunda og'riq ehtimoli: {forecast.pain_probability_30d * 100:.0f}%"
        )
        lines.append(f"  Tavsiya: {forecast.recommendation}")
    else:
        lines.append("- Forecast: yetarli ma'lumot yo'q (kamida 2 kun kerak)")

    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="PostureAI Desktop MVP")
    parser.add_argument("--config", default="config.json", help="Config fayli yo'li")
    parser.add_argument("--db-path", default="posture.db", help="SQLite baza yo'li")
    parser.add_argument("--doctor", action="store_true", help="Dependency va kamera diagnostikasi")
    parser.add_argument("--console", action="store_true", help="Tray o'rniga console rejimda ishga tushirish")
    parser.add_argument("--visual", action="store_true", help="Kamera oynasi va overlay bilan visual sinov rejimi")
    parser.add_argument("-d", "--hide-debug-lines", action="store_true", help="Visual rejimni landmark chiziqlarisiz boshlash")
    parser.add_argument("--calibrate", action="store_true", help="Shaxsiy posture threshold larini kalibrovka qilish")
    parser.add_argument("--calibration-seconds", type=int, help="Kalibrovka davomiyligi (sekund)")
    parser.add_argument("--stats", action="store_true", help="Bugungi va haftalik posture statistikasini chiqarish")
    args = parser.parse_args()

    configure_logging()
    config = load_config(args.config)

    if args.doctor:
        return run_doctor(config, args.db_path)

    if args.stats:
        print(render_stats_report(config, args.db_path))
        return 0

    try:
        validate_environment()
    except RuntimeError as exc:
        logging.getLogger(__name__).error("%s", exc)
        return 1

    if args.calibrate:
        try:
            calibration_profile = collect_calibration_profile(
                config,
                duration_sec=args.calibration_seconds,
            )
        except RuntimeError as exc:
            logging.getLogger(__name__).error("%s", exc)
            return 1

        config.update(calibration_profile)
        save_config(args.config, config)

        print("PostureAI Calibration")
        print(f"- Saved to: {args.config}")
        print(f"- Samples: {calibration_profile['calibration_samples']}")
        print(
            "- Thresholds:"
            f" head={calibration_profile['head_angle_threshold']},"
            f" shoulder={calibration_profile['shoulder_diff_threshold']},"
            f" lean={calibration_profile['forward_lean_threshold']}"
        )
        return 0

    storage = Storage(args.db_path)
    storage.initialize()
    session_id = storage.start_session()

    if args.visual:
        from visual import run_visual_loop

        try:
            run_visual_loop(storage, session_id, config, show_landmarks=not args.hide_debug_lines)
        except KeyboardInterrupt:
            logging.getLogger(__name__).info("Visual rejim to'xtatildi.")
        finally:
            storage.end_session(session_id)
        return 0

    signal_queue: queue.Queue[Any] = queue.Queue()
    stats_queue: queue.Queue[Any] = queue.Queue()
    stop_event = threading.Event()

    detector_thread = threading.Thread(
        target=run_detection_loop,
        args=(signal_queue, stats_queue, stop_event, config),
        daemon=True,
    )
    detector_thread.start()

    try:
        if args.console:
            run_console_app(signal_queue, stats_queue, storage, session_id, stop_event, config)
        else:
            run_app(signal_queue, stats_queue, storage, session_id, stop_event, config)
    finally:
        stop_event.set()
        detector_thread.join(timeout=2)
        storage.end_session(session_id)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
