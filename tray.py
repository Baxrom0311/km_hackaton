from __future__ import annotations

import importlib.util
import logging
import queue
import threading
import time
from dataclasses import dataclass
from typing import Any

from dimmer import ScreenDimmer
from notifier import send_notification

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class RuntimeState:
    latest_status: str = "off"
    today_good_pct: float = 0.0
    today_avg_score: float = 0.0
    today_avg_ergonomic: float = 0.0
    latest_score: int = 0
    latest_ergonomic: int = 0
    latest_sit_minutes: float = 0.0
    last_logged_at: float = 0.0


def _tray_available() -> bool:
    return importlib.util.find_spec("pystray") is not None and importlib.util.find_spec("PIL") is not None


def _process_queues(
    signal_queue: Any,
    stats_queue: Any,
    storage: Any,
    session_id: int,
    config: dict[str, Any],
    state: RuntimeState,
    dimmer: ScreenDimmer | None = None,
) -> bool:
    should_refresh_ui = False
    should_refresh_stats = False

    while True:
        try:
            alert = signal_queue.get_nowait()
        except queue.Empty:
            break
        send_notification("PostureAI", issues=getattr(alert, "issues", []))
        storage.log_alert(getattr(alert, "issues", []), timestamp=getattr(alert, "timestamp", None))
        if dimmer and config.get("dim_on_bad_posture", True):
            dimmer.dim()
        should_refresh_ui = True
        should_refresh_stats = True

    latest_result = None
    while True:
        try:
            latest_result = stats_queue.get_nowait()
        except queue.Empty:
            break

    if latest_result is not None:
        should_refresh_ui = True
        state.latest_status = "off" if getattr(latest_result, "skipped", False) else getattr(latest_result, "status", "off")
        state.latest_score = int(getattr(latest_result, "posture_score", 0) or 0)
        state.latest_ergonomic = int(getattr(latest_result, "ergonomic_score", 0) or 0)
        state.latest_sit_minutes = float(getattr(latest_result, "sit_seconds", 0.0) or 0.0) / 60.0
        if dimmer and state.latest_status == "good" and dimmer.is_dimmed:
            dimmer.restore()
        now = time.monotonic()
        interval = float(config.get("stats_log_interval_seconds", 60))
        should_log = not getattr(latest_result, "skipped", False) and (
            state.last_logged_at == 0.0 or (now - state.last_logged_at) >= interval
        )
        if should_log:
            storage.log_posture(session_id, latest_result)
            state.last_logged_at = now
            should_refresh_stats = True

    if should_refresh_stats:
        today_stats = storage.get_today_stats()
        state.today_good_pct = float(today_stats["good_pct"])
        state.today_avg_score = float(today_stats["avg_score"])
        state.today_avg_ergonomic = float(today_stats.get("avg_ergonomic", 0.0))
    return should_refresh_ui


def run_console_app(
    signal_queue: Any,
    stats_queue: Any,
    storage: Any,
    session_id: int,
    stop_event: Any,
    config: dict[str, Any],
) -> None:
    state = RuntimeState()
    dimmer = ScreenDimmer(dim_level=float(config.get("dim_level", 0.4)))
    logger.info("Monitoring ishga tushdi. To'xtatish uchun Ctrl+C bosing.")

    try:
        while not stop_event.is_set():
            _process_queues(signal_queue, stats_queue, storage, session_id, config, state, dimmer)
            stop_event.wait(0.25)
    except KeyboardInterrupt:
        logger.info("Monitoring to'xtatilyapti.")
        stop_event.set()
    finally:
        dimmer.restore()


def _create_icon(status: str) -> Any:
    from PIL import Image, ImageDraw

    colors = {
        "good": "#2E8B57",
        "bad": "#B22222",
        "off": "#6B7280",
    }
    image = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.ellipse((8, 8, 56, 56), fill=colors.get(status, colors["off"]))
    return image


def _run_tray_app(
    signal_queue: Any,
    stats_queue: Any,
    storage: Any,
    session_id: int,
    stop_event: Any,
    config: dict[str, Any],
) -> None:
    import pystray

    state = RuntimeState()

    def on_exit(icon: Any, _item: Any) -> None:
        stop_event.set()
        icon.stop()

    def monitoring_label(_item: Any) -> str:
        if state.latest_status == "off":
            return "Monitoring: Kutilmoqda"
        if state.latest_status == "bad":
            return "Monitoring: Noto'g'ri holat"
        return "Monitoring: Yaxshi holat"

    def stats_label(_item: Any) -> str:
        return f"Bugun: {state.today_good_pct:.1f}% | posture {state.today_avg_score:.1f} | ergo {state.today_avg_ergonomic:.1f}"

    def sit_label(_item: Any) -> str:
        return f"Hozir uzluksiz o'tirish: {state.latest_sit_minutes:.1f} daqiqa"

    icon = pystray.Icon(
        "PostureAI",
        _create_icon("off"),
        "PostureAI",
        menu=pystray.Menu(
            pystray.MenuItem(monitoring_label, lambda _icon, _item: None, enabled=False),
            pystray.MenuItem(stats_label, lambda _icon, _item: None, enabled=False),
            pystray.MenuItem(sit_label, lambda _icon, _item: None, enabled=False),
            pystray.MenuItem("Chiqish", on_exit),
        ),
    )

    dimmer = ScreenDimmer(dim_level=float(config.get("dim_level", 0.4)))

    def pump() -> None:
        while not stop_event.is_set():
            updated = _process_queues(signal_queue, stats_queue, storage, session_id, config, state, dimmer)
            if updated:
                desired_icon = "good" if state.latest_status == "good" else "bad" if state.latest_status == "bad" else "off"
                icon.icon = _create_icon(desired_icon)
                icon.title = (
                    f"PostureAI | posture {state.latest_score} | "
                    f"ergo {state.latest_ergonomic} | sit {state.latest_sit_minutes:.0f}m"
                )
                icon.update_menu()
            stop_event.wait(0.5)
        icon.stop()

    worker = threading.Thread(target=pump, daemon=True)
    worker.start()
    try:
        icon.run()
    finally:
        dimmer.restore()
    stop_event.set()
    worker.join(timeout=2)


def run_app(
    signal_queue: Any,
    stats_queue: Any,
    storage: Any,
    session_id: int,
    stop_event: Any,
    config: dict[str, Any],
) -> None:
    if _tray_available():
        try:
            _run_tray_app(signal_queue, stats_queue, storage, session_id, stop_event, config)
            return
        except Exception:
            logger.exception("Tray UI ishga tushmadi, console fallback ishlatiladi.")

    run_console_app(signal_queue, stats_queue, storage, session_id, stop_event, config)
