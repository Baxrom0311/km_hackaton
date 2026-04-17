from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from detector import PostureResult
from main import DEFAULT_CONFIG, load_config, render_stats_report, save_config
from storage import Storage


class MainTests(unittest.TestCase):
    def test_load_config_uses_defaults_when_file_missing(self) -> None:
        config = load_config("missing-config.json")
        self.assertEqual(config["fps"], DEFAULT_CONFIG["fps"])
        self.assertEqual(config["camera_index"], DEFAULT_CONFIG["camera_index"])

    def test_load_config_overrides_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "config.json"
            config_path.write_text(
                json.dumps({"fps": 15, "camera_index": 2}),
                encoding="utf-8",
            )

            config = load_config(str(config_path))

            self.assertEqual(config["fps"], 15)
            self.assertEqual(config["camera_index"], 2)
            self.assertEqual(config["language"], DEFAULT_CONFIG["language"])

    def test_save_config_round_trips(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "config.json"
            payload = dict(DEFAULT_CONFIG)
            payload["fps"] = 22
            payload["baseline_head_angle"] = 11.4

            save_config(str(config_path), payload)
            loaded = load_config(str(config_path))

            self.assertEqual(loaded["fps"], 22)
            self.assertEqual(loaded["baseline_head_angle"], 11.4)

    def test_render_stats_report_contains_summary(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "posture.db"
            storage = Storage(str(db_path))
            storage.initialize()
            session_id = storage.start_session()
            storage.log_posture(
                session_id,
                PostureResult(
                    status="good",
                    head_angle=5.0,
                    shoulder_diff=0.01,
                    forward_lean=-0.05,
                    posture_score=90,
                ),
            )
            storage.log_alert(["Boshingizni ko'taring!"])
            storage.end_session(session_id)

            config = dict(DEFAULT_CONFIG)
            config["baseline_head_angle"] = 10.0
            config["baseline_shoulder_diff"] = 0.01
            config["baseline_forward_lean"] = -0.05

            report = render_stats_report(config, str(db_path))

            self.assertIn("PostureAI Stats", report)
            self.assertIn("Today: good=100.0% bad=0.0% avg_score=90.0", report)
            self.assertIn("Calibration: head=10.0, shoulder=0.01, lean=-0.05", report)


if __name__ == "__main__":
    unittest.main()
