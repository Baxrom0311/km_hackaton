from pathlib import Path
from pydantic import BaseModel, ConfigDict, Field
import json
from loguru import logger
import os

class AppConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    head_angle_threshold: float = Field(default=25.0, ge=5.0, le=60.0, description="Boshingizni oldinga egishning taqiqlangan darajasi (gradus)")
    shoulder_diff_threshold: float = Field(default=0.07, ge=0.01, le=0.5, description="Yelkalar orasidagi farqning ruxsat etilgan chegarasi (normallashgan)")
    forward_lean_threshold: float = Field(default=-0.35, ge=-1.0, le=0.0, description="Oldinga engashish chegarasi")

    temporal_window_size: int = Field(default=90, ge=10, le=300, description="Datchiklarning yodida saqlanadigan ramkalar soni")
    temporal_threshold: float = Field(default=0.7, ge=0.1, le=1.0, description="Signal yuborish uchun xato ramkalar foizi")
    cooldown_seconds: int = Field(default=60, ge=5, le=600, description="Bildirishnomalar orasidagi vaqt")

    camera_index: int = Field(default=0, ge=0, le=10)
    fps: int = Field(default=5, ge=1, le=30, description="5 FPS yetarli — posture sekin o'zgaradi")
    camera_width: int = Field(default=640, ge=320, le=1920, description="Kamera resolution kengligi")
    camera_height: int = Field(default=480, ge=240, le=1080, description="Kamera resolution balandligi")
    language: str = Field(default="uz")

    min_visibility: float = Field(default=0.3, ge=0.1, le=1.0)
    model_complexity: int = Field(default=1, ge=0, le=2)
    min_detection_confidence: float = Field(default=0.4, ge=0.1, le=1.0)
    min_pose_presence_confidence: float = Field(default=0.4, ge=0.1, le=1.0)
    min_tracking_confidence: float = Field(default=0.4, ge=0.1, le=1.0)
    ai_skip_frames: int = Field(default=2, ge=1, le=10, description="Har N-chi kadrda AI ishlaydi (CPU tejash)")

    stats_log_interval_seconds: int = Field(default=60, ge=10, le=600)
    calibration_seconds: int = Field(default=12, ge=5, le=60)
    calibration_min_samples: int = Field(default=25, ge=5, le=200)

    baseline_head_angle: float | None = None
    baseline_shoulder_diff: float | None = None
    baseline_forward_lean: float | None = None

    model_asset_path: str = "models/pose_landmarker_heavy.task"

    start_minimized: bool = False

    sit_break_threshold_seconds: int = Field(default=60, ge=30, le=600)
    sit_alert_threshold_seconds: int = Field(default=1500, ge=300, le=7200)
    sit_alert_cooldown_seconds: int = Field(default=300, ge=60, le=1800)

def get_config_path() -> Path:
    app_data_dir = Path(os.getenv("APPDATA", "~")).expanduser() if os.name == "nt" else Path.home() / ".config" / "PostureAI"
    if not app_data_dir.exists():
        app_data_dir.mkdir(parents=True, exist_ok=True)
    return app_data_dir / "config.json"

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
