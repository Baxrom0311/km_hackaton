from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from posture_ai.vision.detector import PostureResult
from posture_ai.database.storage import Storage


class StorageTests(unittest.TestCase):
    def test_logs_are_persisted_and_reported(self) -> None:
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
                    posture_score=92,
                ),
            )
            storage.log_posture(
                session_id,
                PostureResult(
                    status="bad",
                    head_angle=31.0,
                    shoulder_diff=0.12,
                    forward_lean=-0.32,
                    posture_score=28,
                    issues=["Oldinga engashmang!"],
                ),
            )
            storage.log_alert(["Oldinga engashmang!"])
            storage.end_session(session_id)

            today_stats = storage.get_today_stats()
            weekly_summary = storage.get_weekly_summary()

            self.assertEqual(today_stats["good_pct"], 50.0)
            self.assertEqual(today_stats["bad_pct"], 50.0)
            self.assertEqual(today_stats["avg_score"], 60.0)
            self.assertEqual(today_stats["total_samples"], 2)
            self.assertEqual(today_stats["alerts_count"], 1)
            self.assertEqual(len(weekly_summary), 1)
            self.assertEqual(weekly_summary[0]["good_pct"], 50.0)
            self.assertEqual(weekly_summary[0]["avg_score"], 60.0)


if __name__ == "__main__":
    unittest.main()
