from pathlib import Path
from pydantic import BaseModel, ConfigDict, Field
from pydantic.json import pydantic_encoder
import json
from loguru import logger
import os

class AppConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    head_angle_threshold: float = Field(default=25.0, description="Boshingizni oldinga egishning taqiqlangan darajasi (gradus)")
    shoulder_diff_threshold: float = Field(default=0.07, description="Yelkalar orasidagi farqning ruxsat etilgan chegarasi (normallashgan)")
    forward_lean_threshold: float = Field(default=-0.2, description="Oldinga engashish chegarasi")
    
    temporal_window_size: int = Field(default=90, description="Datchiklarning yodida saqlanadigan ramkalar soni")
    temporal_threshold: float = Field(default=0.7, description="Signal yuborish uchun xato ramkalar foizi")
    cooldown_seconds: int = Field(default=60, description="Bildirishnomalar orasidagi vaqt")
    
    camera_index: int = Field(default=0)
    fps: int = Field(default=10)
    language: str = Field(default="uz")
    
    min_visibility: float = 0.5
    model_complexity: int = 2
    min_detection_confidence: float = 0.5
    min_pose_presence_confidence: float = 0.5
    min_tracking_confidence: float = 0.5
    
    stats_log_interval_seconds: int = 60
    calibration_seconds: int = 12
    calibration_min_samples: int = 25
    
    baseline_head_angle: float | None = None
    baseline_shoulder_diff: float | None = None
    baseline_forward_lean: float | None = None
    
    model_asset_path: str = "models/pose_landmarker_heavy.task"
    
    sit_break_threshold_seconds: int = 60
    sit_alert_threshold_seconds: int = 1500
    sit_alert_cooldown_seconds: int = 300

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
