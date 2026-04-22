from pathlib import Path
from pydantic import BaseModel, ConfigDict, Field
import json
from posture_ai.core.logger import logger
import os
import sys
import tempfile

class AppConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    head_angle_threshold: float = Field(default=25.0, ge=5.0, le=60.0, description="Boshingizni oldinga egishning taqiqlangan darajasi (gradus)")
    shoulder_diff_threshold: float = Field(default=0.07, ge=0.01, le=0.5, description="Yelkalar orasidagi farqning ruxsat etilgan chegarasi (normallashgan)")
    forward_lean_threshold: float = Field(default=-0.35, ge=-1.0, le=0.0, description="Oldinga engashish chegarasi")

    temporal_window_size: int = Field(default=90, ge=10, le=300, description="Datchiklarning yodida saqlanadigan ramkalar soni")
    temporal_threshold: float = Field(default=0.7, ge=0.1, le=1.0, description="Signal yuborish uchun xato ramkalar foizi")
    cooldown_seconds: int = Field(default=60, ge=5, le=600, description="Bildirishnomalar orasidagi vaqt")

    camera_index: int = Field(default=0, ge=0, le=10)
    fps: int = Field(default=30, ge=1, le=60, description="Kamera uchun FPS (30 standart, AI uchun ai_skip_frames ishlatiladi)")
    preview_fps: int = Field(default=15, ge=1, le=30, description="Dashboard live preview FPS")
    camera_width: int = Field(default=640, ge=320, le=1920, description="Kamera resolution kengligi")
    camera_height: int = Field(default=480, ge=240, le=1080, description="Kamera resolution balandligi")
    ai_frame_width: int = Field(default=480, ge=256, le=1280, description="AI inferensiya uchun frame kengligi")
    language: str = Field(default="uz")

    min_visibility: float = Field(default=0.3, ge=0.1, le=1.0)
    model_complexity: int = Field(default=1, ge=0, le=2)
    min_detection_confidence: float = Field(default=0.4, ge=0.1, le=1.0)
    min_pose_presence_confidence: float = Field(default=0.4, ge=0.1, le=1.0)
    min_tracking_confidence: float = Field(default=0.4, ge=0.1, le=1.0)
    ai_skip_frames: int = Field(default=6, ge=1, le=30, description="Har N-chi kadrda AI ishlaydi (CPU tejash)")

    stats_log_interval_seconds: int = Field(default=60, ge=10, le=600)
    calibration_seconds: int = Field(default=12, ge=5, le=60)
    calibration_min_samples: int = Field(default=25, ge=5, le=200)

    baseline_head_angle: float | None = None
    baseline_shoulder_diff: float | None = None
    baseline_forward_lean: float | None = None
    baseline_roll_xy_deg: float | None = None
    baseline_yaw_xz_deg: float | None = None
    baseline_pitch_yz_deg: float | None = None

    roll_xy_threshold_deg: float = Field(default=12.0, ge=3.0, le=45.0)
    yaw_xz_threshold_deg: float = Field(default=18.0, ge=3.0, le=60.0)
    pitch_yz_threshold_deg: float = Field(default=18.0, ge=3.0, le=60.0)
    shoulder_elevation_threshold: float = Field(default=0.75, ge=0.2, le=1.0)

    model_asset_path: str = "models/pose_landmarker_heavy.task"

    start_minimized: bool = False

    sit_break_threshold_seconds: int = Field(default=60, ge=30, le=600)
    sit_alert_threshold_seconds: int = Field(default=1500, ge=300, le=7200)
    sit_alert_cooldown_seconds: int = Field(default=300, ge=60, le=1800)
    fatigue_alert_threshold: int = Field(default=65, ge=20, le=95)
    fatigue_alert_cooldown_seconds: int = Field(default=600, ge=60, le=3600)

def get_app_data_dir() -> Path:
    if os.name == "nt":
        app_data_dir = Path(os.getenv("APPDATA", "~")).expanduser() / "PostureAI"
    else:
        app_data_dir = Path.home() / ".config" / "PostureAI"
    try:
        app_data_dir.mkdir(parents=True, exist_ok=True)
        return app_data_dir
    except OSError as exc:
        logger.warning("App data papkasiga yozib bo'lmadi ({}), lokal fallback ishlatiladi", exc)

    fallback_dir = Path(tempfile.gettempdir()) / "PostureAI"
    try:
        fallback_dir.mkdir(parents=True, exist_ok=True)
        return fallback_dir
    except OSError:
        local_dir = Path.cwd() / "local_test_logs" / "PostureAI"
        local_dir.mkdir(parents=True, exist_ok=True)
        return local_dir


def get_config_path() -> Path:
    return get_app_data_dir() / "config.json"


def get_default_db_path() -> Path:
    return get_app_data_dir() / "posture.db"


def resolve_model_asset_path(model_asset_path: str | Path) -> Path:
    """Model faylini CWD, source tree, PyInstaller va installed data'dan izlaydi."""
    raw_path = Path(model_asset_path).expanduser()
    if raw_path.is_absolute():
        return raw_path

    candidates: list[Path] = [Path.cwd() / raw_path]

    frozen_root = getattr(sys, "_MEIPASS", None)
    if frozen_root:
        candidates.append(Path(frozen_root) / raw_path)

    package_root = Path(__file__).resolve().parents[1]
    source_root = Path(__file__).resolve().parents[3]
    candidates.extend(
        [
            source_root / raw_path,
            package_root / raw_path,
            Path(sys.executable).resolve().parent / raw_path,
            Path(sys.prefix) / "share" / "posture-ai" / raw_path,
            Path(sys.base_prefix) / "share" / "posture-ai" / raw_path,
        ]
    )

    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


def load_config(path: str | Path | None = None) -> AppConfig:
    conf_path = Path(path) if path else get_config_path()
    
    if not conf_path.exists():
        logger.info(f"Yangi config fayli yaratilmoqda: {conf_path}")
        default_config = AppConfig()
        save_config(default_config, conf_path)
        return default_config
    
    try:
        data = json.loads(conf_path.read_text(encoding="utf-8"))
        cfg = AppConfig(**data)
        logger.debug(f"Config muvaffaqiyatli yuklandi: {conf_path}")
        return cfg
    except Exception as e:
        logger.error(f"Config faylni oqishda xatolik yuz berdi: {e}. Standart rejim yoqilmoqda.")
        return AppConfig()

def save_config(config: AppConfig, path: str | Path | None = None) -> None:
    conf_path = Path(path) if path else get_config_path()
    try:
        conf_path.parent.mkdir(parents=True, exist_ok=True)
        conf_path.write_text(config.model_dump_json(indent=2), encoding="utf-8")
        logger.info(f"Config saqlandi: {conf_path}")
    except Exception as e:
        logger.error(f"Config saqlashda xatoli: {e}")
