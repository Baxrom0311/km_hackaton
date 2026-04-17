"""Forecast slaydi va demo video uchun 7 kunlik realistik ma'lumot seed qiladi.

Ishga tushirish:
    python tools/seed_demo_data.py

Diqqat: mavjud `posture.db` dagi sessions/posture_logs jadvallariga qo'shimcha
qatorlar yozadi. Toza boshlash uchun avval `posture.db` ni o'chiring.
"""

from __future__ import annotations

import datetime
import random
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from storage import Storage  # noqa: E402

DB_PATH = ROOT / "posture.db"


def main() -> None:
    storage = Storage(str(DB_PATH))
    storage.initialize()

    connection = sqlite3.connect(str(DB_PATH))
    cursor = connection.cursor()

    cursor.execute(
        "INSERT INTO sessions (start_time) VALUES (datetime('now', '-7 days'))"
    )
    session_id = cursor.lastrowid

    # Trend: dastlab yaxshi, kunlar o'tgani sari yomonlashadi
    for day_offset in range(7, 0, -1):
        base_score = 88 - (7 - day_offset) * 4
        for minute in range(60):
            ts = (
                datetime.datetime.now()
                - datetime.timedelta(days=day_offset, minutes=minute)
            ).isoformat(timespec="seconds")
            score = max(20, min(100, base_score + random.randint(-8, 8)))
            ergo = max(20, score - random.randint(0, 15))
            status = "good" if score >= 70 else "bad"
            cursor.execute(
                """
                INSERT INTO posture_logs (
                    session_id, timestamp, status,
                    head_angle, shoulder_diff, forward_lean,
                    posture_score, ergonomic_score, sit_seconds, face_distance
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    ts,
                    status,
                    15.0 + random.uniform(-3, 12),
                    0.04 + random.uniform(0, 0.05),
                    -0.10 + random.uniform(-0.15, 0.05),
                    score,
                    ergo,
                    minute * 60,
                    0.20 + random.uniform(-0.05, 0.15),
                ),
            )

    connection.commit()
    connection.close()
    print(f"Seeded 7 kunlik demo ma'lumot: {DB_PATH}")
    print("Endi ishga tushiring: python main.py --stats")


if __name__ == "__main__":
    main()
