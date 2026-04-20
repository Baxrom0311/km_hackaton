from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Generator, Sequence


@dataclass(slots=True)
class Storage:
    path: str = "posture.db"

    @contextmanager
    def _connect(self) -> Generator[sqlite3.Connection, None, None]:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _ensure_posture_log_columns(self, connection: sqlite3.Connection) -> None:
        existing_columns = {
            row["name"] for row in connection.execute("PRAGMA table_info(posture_logs)").fetchall()
        }
        if "posture_score" not in existing_columns:
            connection.execute("ALTER TABLE posture_logs ADD COLUMN posture_score REAL")
        if "ergonomic_score" not in existing_columns:
            connection.execute("ALTER TABLE posture_logs ADD COLUMN ergonomic_score REAL")
        if "sit_seconds" not in existing_columns:
            connection.execute("ALTER TABLE posture_logs ADD COLUMN sit_seconds REAL")
        if "face_distance" not in existing_columns:
            connection.execute("ALTER TABLE posture_logs ADD COLUMN face_distance REAL")

    def initialize(self) -> None:
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    start_time TEXT NOT NULL,
                    end_time TEXT
                );

                CREATE TABLE IF NOT EXISTS posture_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id INTEGER REFERENCES sessions(id),
                    timestamp TEXT NOT NULL,
                    status TEXT NOT NULL,
                    head_angle REAL,
                    shoulder_diff REAL,
                    forward_lean REAL,
                    posture_score REAL,
                    ergonomic_score REAL,
                    sit_seconds REAL,
                    face_distance REAL
                );

                CREATE TABLE IF NOT EXISTS alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    issues TEXT
                );
                """
            )
            self._ensure_posture_log_columns(connection)

    def start_session(self) -> int:
        started_at = datetime.now().isoformat(timespec="seconds")
        with self._connect() as connection:
            cursor = connection.execute(
                "INSERT INTO sessions (start_time) VALUES (?)",
                (started_at,),
            )
            return int(cursor.lastrowid)

    def end_session(self, session_id: int) -> None:
        ended_at = datetime.now().isoformat(timespec="seconds")
        with self._connect() as connection:
            connection.execute(
                "UPDATE sessions SET end_time = ? WHERE id = ?",
                (ended_at, session_id),
            )

    def log_posture(self, session_id: int, result: Any) -> None:
        if getattr(result, "skipped", False):
            return

        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO posture_logs (
                    session_id,
                    timestamp,
                    status,
                    head_angle,
                    shoulder_diff,
                    forward_lean,
                    posture_score,
                    ergonomic_score,
                    sit_seconds,
                    face_distance
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    getattr(result, "timestamp", datetime.now().isoformat(timespec="seconds")),
                    getattr(result, "status", "unknown"),
                    getattr(result, "head_angle", None),
                    getattr(result, "shoulder_diff", None),
                    getattr(result, "forward_lean", None),
                    getattr(result, "posture_score", None),
                    getattr(result, "ergonomic_score", None),
                    getattr(result, "sit_seconds", None),
                    getattr(result, "face_distance", None),
                ),
            )

    def log_alert(self, issues: Sequence[str], timestamp: str | None = None) -> None:
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO alerts (timestamp, issues) VALUES (?, ?)",
                (
                    timestamp or datetime.now().isoformat(timespec="seconds"),
                    json.dumps(list(issues), ensure_ascii=False),
                ),
            )

    def get_today_stats(self) -> dict[str, float | int]:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT
                    COUNT(*) AS total,
                    SUM(CASE WHEN status = 'good' THEN 1 ELSE 0 END) AS good_count,
                    SUM(CASE WHEN status = 'bad' THEN 1 ELSE 0 END) AS bad_count,
                    AVG(posture_score) AS avg_score,
                    AVG(ergonomic_score) AS avg_ergonomic,
                    MAX(sit_seconds) AS max_sit_seconds
                FROM posture_logs
                WHERE DATE(timestamp) = DATE('now', 'localtime')
                """
            ).fetchone()
            alerts_row = connection.execute(
                """
                SELECT COUNT(*) AS alerts_count
                FROM alerts
                WHERE DATE(timestamp) = DATE('now', 'localtime')
                """
            ).fetchone()

        total = int(row["total"] or 0)
        good_count = int(row["good_count"] or 0)
        bad_count = int(row["bad_count"] or 0)
        good_pct = round((100.0 * good_count / total), 1) if total else 0.0
        bad_pct = round((100.0 * bad_count / total), 1) if total else 0.0
        avg_score = round(float(row["avg_score"] or 0.0), 1)
        avg_ergonomic = round(float(row["avg_ergonomic"] or 0.0), 1)
        max_sit_seconds = float(row["max_sit_seconds"] or 0.0)

        return {
            "good_pct": good_pct,
            "bad_pct": bad_pct,
            "avg_score": avg_score,
            "avg_ergonomic": avg_ergonomic,
            "max_sit_seconds": max_sit_seconds,
            "total_samples": total,
            "alerts_count": int(alerts_row["alerts_count"] or 0),
        }

    def get_today_frequent_issues(self) -> list[tuple[str, int]]:
        """Bugungi eng ko'p uchraydigan muammolar (kamayish tartibida)."""
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT issues FROM alerts
                WHERE DATE(timestamp) = DATE('now', 'localtime')
                """
            ).fetchall()

        from collections import Counter
        counter: Counter[str] = Counter()
        for row in rows:
            raw = row["issues"]
            if raw:
                try:
                    items = json.loads(raw)
                    for item in items:
                        counter[item] += 1
                except (json.JSONDecodeError, TypeError):
                    pass
        return counter.most_common()

    def get_weekly_summary(self) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    DATE(timestamp) AS day,
                    COUNT(*) AS total,
                    SUM(CASE WHEN status = 'good' THEN 1 ELSE 0 END) AS good_count,
                    SUM(CASE WHEN status = 'bad' THEN 1 ELSE 0 END) AS bad_count,
                    AVG(posture_score) AS avg_score,
                    AVG(ergonomic_score) AS avg_ergonomic
                FROM posture_logs
                WHERE DATE(timestamp) >= DATE('now', '-6 days', 'localtime')
                GROUP BY DATE(timestamp)
                ORDER BY DATE(timestamp) ASC
                """
            ).fetchall()

        summary: list[dict[str, Any]] = []
        for row in rows:
            total = int(row["total"] or 0)
            good_count = int(row["good_count"] or 0)
            summary.append(
                {
                    "day": row["day"],
                    "total": total,
                    "good_pct": round((100.0 * good_count / total), 1) if total else 0.0,
                    "bad_count": int(row["bad_count"] or 0),
                    "avg_score": round(float(row["avg_score"] or 0.0), 1),
                    "avg_ergonomic": round(float(row["avg_ergonomic"] or 0.0), 1),
                }
            )
        return summary
