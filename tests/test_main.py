from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
import json
import os

from posture_ai.vision.detector import PostureResult
from posture_ai.core.config import AppConfig, load_config, resolve_model_asset_path, save_config
from posture_ai.database.storage import Storage
from posture_ai.main import render_stats_report


class MainTests(unittest.TestCase):
    def test_load_config_uses_defaults_when_file_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "missing-config.json"

            config = load_config(str(config_path))
            default_config = AppConfig()

            self.assertEqual(config.fps, default_config.fps)
            self.assertEqual(config.camera_index, default_config.camera_index)
            self.assertTrue(config_path.exists())

    def test_load_config_overrides_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "config.json"
            config_path.write_text(
                json.dumps({"fps": 15, "camera_index": 2}),
                encoding="utf-8",
            )

            config = load_config(str(config_path))

            self.assertEqual(config.fps, 15)
            self.assertEqual(config.camera_index, 2)
            self.assertEqual(config.language, AppConfig().language)

    def test_save_config_round_trips(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "config.json"
            payload = AppConfig()
            payload.fps = 22
            payload.baseline_head_angle = 11.4

            save_config(payload, str(config_path))
            loaded = load_config(str(config_path))

            self.assertEqual(loaded.fps, 22)
            self.assertEqual(loaded.baseline_head_angle, 11.4)

    def test_render_stats_report_includes_summary_counts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "posture.db"
            storage = Storage(str(db_path))
            storage.initialize()

            session_id = storage.start_session()
            storage.log_posture(
                session_id,
                PostureResult(
                    status="good",
                    head_angle=10.0,
                    shoulder_diff=0.01,
                    forward_lean=-0.05,
                    posture_score=90,
                    ergonomic_score=88,
                    sit_seconds=120.0,
                    face_distance=0.12,
                ),
            )
            storage.log_alert(["Tanaffus qiling!"])
            storage.end_session(session_id)

            report = render_stats_report(AppConfig(), db_path=db_path)

            self.assertIn("PostureAI Stats", report)
            self.assertIn("Samples: 1 | Alerts: 1", report)

    def test_model_asset_path_resolves_outside_project_cwd(self) -> None:
        old_cwd = Path.cwd()
        with tempfile.TemporaryDirectory() as temp_dir:
            os.chdir(temp_dir)
            try:
                resolved = resolve_model_asset_path("models/pose_landmarker_heavy.task")
            finally:
                os.chdir(old_cwd)

        self.assertTrue(resolved.exists())
        self.assertEqual(resolved.name, "pose_landmarker_heavy.task")


if __name__ == "__main__":
    unittest.main()
