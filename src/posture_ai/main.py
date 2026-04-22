"""PostureAI — dasturni ishga tushirish va servis utilitalari.

Ishga tushirish rejimlari:
  python main.py                → Dashboard oynasi ochiladi + tray icon
  python main.py --background   → Faqat tray icon (oyna yo'q)
  python main.py --doctor       → Kamera/model/dependency diagnostikasi
  python main.py --stats        → Joriy statistika va forecast hisoboti
"""

from __future__ import annotations

import argparse
import os
import signal
import sys
import threading
from pathlib import Path

from posture_ai.core.logger import logger

from posture_ai.core.config import (
    AppConfig,
    get_app_data_dir,
    get_default_db_path,
    load_config,
    resolve_model_asset_path,
)
from posture_ai.core.forecast import forecast_risk
from posture_ai.database.storage import Storage
from posture_ai.vision.detector import PoseDetector, check_runtime_dependencies

# SDL2 duplicate library warning'larni bostiramiz (cv2 + pygame konflikt)
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")


def configure_logging() -> None:
    log_dir = get_app_data_dir() / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    logger.add(
        str(log_dir / "posture_ai_{time}.log"),
        rotation="5 MB",
        retention="10 days",
        level="INFO",
    )
    logger.info("Dastur ishga tushirildi.")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="PostureAI — Ergonomik monitoring tizimi")
    parser.add_argument(
        "--background",
        "--bg",
        action="store_true",
        help="Orqa fon rejimi — faqat tray icon, oyna ko'rsatilmaydi",
    )
    parser.add_argument(
        "--doctor",
        action="store_true",
        help="Model, dependency va kamera holatini tekshiradi",
    )
    parser.add_argument(
        "--stats",
        action="store_true",
        help="Bugungi statistika va forecast hisobotini chiqaradi",
    )
    return parser.parse_args(argv)


def build_storage(db_path: str | Path | None = None) -> Storage:
    resolved_path = Path(db_path) if db_path else get_default_db_path()
    storage = Storage(str(resolved_path))
    storage.initialize()
    return storage


def render_stats_report(config: AppConfig, db_path: str | Path | None = None) -> str:
    storage = build_storage(db_path)

    today = storage.get_today_stats()
    weekly = storage.get_weekly_summary()
    forecast = forecast_risk(weekly)

    lines = [
        "PostureAI Stats",
        (
            f"- Today: good={today['good_pct']:.1f}% bad={today['bad_pct']:.1f}% "
            f"avg_score={today['avg_score']:.1f}"
        ),
        (
            f"- Ergonomic: avg={today['avg_ergonomic']:.1f} | "
            f"longest_sit={float(today['max_sit_seconds']) / 60.0:.1f} min"
        ),
        f"- Samples: {int(today['total_samples'])} | Alerts: {int(today['alerts_count'])}",
        (
            "- Calibration: "
            f"head={config.baseline_head_angle}, "
            f"shoulder={config.baseline_shoulder_diff}, "
            f"lean={config.baseline_forward_lean}"
        ),
        (
            "- 3D Calibration: "
            f"xy={config.baseline_roll_xy_deg}, "
            f"xz={config.baseline_yaw_xz_deg}, "
            f"yz={config.baseline_pitch_yz_deg}"
        ),
    ]

    if weekly:
        lines.append("- Weekly:")
        for row in weekly:
            lines.append(
                "  "
                f"{row['day']} | good={row['good_pct']:.1f}% | "
                f"posture={row['avg_score']:.1f} | ergo={row['avg_ergonomic']:.1f} | "
                f"bad={int(row['bad_count'])}"
            )

    if forecast is None:
        lines.append("- Forecast: ma'lumot yetarli emas (kamida 2 kunlik tarix kerak)")
    else:
        lines.extend(
            [
                "- Forecast:",
                (
                    f"  current_risk={forecast.current_risk:.1f} ({forecast.category}) | "
                    f"7d_projected={forecast.projected_risk_7d:.1f} | "
                    f"slope/day={forecast.slope_per_day:+.2f}"
                ),
                f"  30 kunda og'riq ehtimoli: {forecast.pain_probability_30d * 100:.0f}%",
                (
                    f"  Model: R²={forecast.r_squared:.3f} | MAPE={forecast.mape:.1f}% | "
                    f"80% CI=[{forecast.confidence_lower:.1f}, {forecast.confidence_upper:.1f}]"
                ),
                f"  Tavsiya: {forecast.recommendation}",
            ]
        )

    return "\n".join(lines)


def run_doctor(config: AppConfig, db_path: str | Path | None = None) -> int:
    storage = build_storage(db_path)
    lines = ["PostureAI Doctor"]
    has_error = False

    lines.append(f"- Config: ok (camera_index={config.camera_index}, fps={config.fps})")
    lines.append(f"- SQLite: ok ({storage.path})")

    missing = check_runtime_dependencies()
    if missing:
        has_error = True
        lines.append(f"- Dependencies: missing ({', '.join(missing)})")
    else:
        lines.append("- Dependencies: ok")

    model_path = resolve_model_asset_path(config.model_asset_path)
    if model_path.exists():
        lines.append(f"- Model: ok ({model_path})")
    else:
        has_error = True
        lines.append(f"- Model: missing ({model_path})")

    if not missing and model_path.exists():
        detector: PoseDetector | None = None
        try:
            detector = PoseDetector(config.model_dump())
            detector.open()
            lines.append(f"- Camera: ok (index={config.camera_index})")
        except Exception as exc:
            has_error = True
            lines.append(f"- Camera: error ({exc})")
        finally:
            if detector is not None:
                try:
                    detector.close()
                except Exception:
                    pass
    else:
        lines.append("- Camera: skipped (dependency/model muammosi bor)")

    print("\n".join(lines))
    return 1 if has_error else 0


def _run_gui(config: AppConfig, storage: Storage, *, start_minimized: bool) -> int:
    from PySide6.QtCore import QSharedMemory
    from PySide6.QtWidgets import QApplication, QMessageBox

    from posture_ai.gui.main_window import DashboardWindow
    from posture_ai.os_utils.audio_helper import prepare_voices

    signal.signal(signal.SIGINT, signal.SIG_DFL)

    app = QApplication(sys.argv)
    app.setApplicationName("PostureAI")
    app.setQuitOnLastWindowClosed(False)

    shared_mem = QSharedMemory("PostureAI_Singleton_Lock")
    if not shared_mem.create(1):
        shared_mem.attach()
        shared_mem.detach()
        if not shared_mem.create(1):
            logger.warning("Dastur allaqachon ishga tushirilgan.")
            msg = QMessageBox()
            msg.setIcon(QMessageBox.Icon.Warning)
            msg.setWindowTitle("Diqqat")
            msg.setText("PostureAI allaqachon ishlamoqda.\nTray ikonkasini tekshiring.")
            msg.exec()
            return 0

    logger.info("Ovozli signallar tayyorlanmoqda...")
    threading.Thread(target=prepare_voices, daemon=True).start()

    window = DashboardWindow(config, storage, start_minimized=start_minimized)
    app.aboutToQuit.connect(window._cleanup_before_quit)

    if not start_minimized:
        window.show()
        logger.info("Dashboard oynasi ochildi.")
    else:
        logger.info("Background rejimda ishga tushdi. Tray ikonkasidan boshqaring.")

    return app.exec()


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    configure_logging()

    config = load_config()

    if args.doctor:
        return run_doctor(config)

    if args.stats:
        print(render_stats_report(config))
        return 0

    storage = build_storage()
    logger.info("Database ulandi.")
    start_minimized = args.background or config.start_minimized
    return _run_gui(config, storage, start_minimized=start_minimized)


if __name__ == "__main__":
    raise SystemExit(main())
