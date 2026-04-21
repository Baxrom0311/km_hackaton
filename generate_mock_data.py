"""PostureAI — Demo uchun 7 kunlik mock ma'lumot generatori.

Hakaton demo'da Predictive Forecast, haftalik trend va bugungi statistika
to'liq ishlashi uchun SQLite bazaga simulatsiya qilingan ma'lumotlar yozadi.

Ssenariy: Foydalanuvchi 7 kun davomida asta-sekin charchaydi,
posture score pasayib boradi → Forecast xavf oshganini ko'rsatadi.
"""

import random
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from posture_ai.core.config import get_default_db_path


def generate_mock_data(db_path: str | None = None) -> None:
    resolved_db_path = db_path or str(get_default_db_path())
    conn = sqlite3.connect(resolved_db_path)
    cursor = conn.cursor()

    # Storage.initialize() dagi sxemaga mos jadvallar
    cursor.executescript("""
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
    """)

    print("Oldingi ma'lumotlar tozalanmoqda...")
    cursor.execute("DELETE FROM posture_logs")
    cursor.execute("DELETE FROM alerts")
    cursor.execute("DELETE FROM sessions")

    today = datetime.now().replace(hour=9, minute=0, second=0, microsecond=0)
    random.seed(42)  # Reproducible natijalar

    # 7 kunlik ssenariy: 1-kun yaxshi (85+), 7-kunga qarab yomonlashadi (55-65)
    # Bu Forecast uchun aniq pasayuvchi trend hosil qiladi
    day_base_scores = [88, 82, 78, 72, 68, 63, 58]

    for day_idx in range(7):
        day_offset = 6 - day_idx  # 6 kun oldindan to bugungacha
        current_date = today - timedelta(days=day_offset)
        base_score = day_base_scores[day_idx]

        # Session ochish
        start_time = current_date.isoformat(timespec="seconds")
        cursor.execute(
            "INSERT INTO sessions (start_time) VALUES (?)", (start_time,)
        )
        session_id = cursor.lastrowid

        # Har kunda 12-18 ta o'lchov (har 5-10 daqiqada bir marta log)
        num_logs = random.randint(12, 18)
        for i in range(num_logs):
            log_time = current_date + timedelta(minutes=i * random.randint(5, 10))
            timestamp = log_time.isoformat(timespec="seconds")

            # Score — base_score atrofida normal taqsimot
            posture_score = max(10, min(100, int(random.gauss(base_score, 8))))
            status = "good" if posture_score >= 60 else "bad"

            # Realistic metriklar
            if status == "good":
                head_angle = round(random.uniform(8.0, 20.0), 1)
                shoulder_diff = round(random.uniform(0.01, 0.05), 4)
                forward_lean = round(random.uniform(-0.12, -0.03), 4)
                face_distance = round(random.uniform(0.14, 0.22), 4)
            else:
                head_angle = round(random.uniform(26.0, 40.0), 1)
                shoulder_diff = round(random.uniform(0.08, 0.15), 4)
                forward_lean = round(random.uniform(-0.35, -0.18), 4)
                face_distance = round(random.uniform(0.25, 0.38), 4)

            sit_seconds = round(300 + i * 300 + random.uniform(-60, 60), 1)

            # Ergonomic score — posture_score dan sit va eye penalty
            sit_penalty = min(25.0, sit_seconds / 5400 * 25)
            eye_penalty = max(0, (face_distance - 0.18) / 0.14) * 15
            ergonomic_score = max(5, min(100, round(
                posture_score - sit_penalty - eye_penalty
            )))

            cursor.execute(
                """INSERT INTO posture_logs
                   (session_id, timestamp, status, head_angle, shoulder_diff,
                    forward_lean, posture_score, ergonomic_score, sit_seconds, face_distance)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (session_id, timestamp, status, head_angle, shoulder_diff,
                 forward_lean, posture_score, ergonomic_score, sit_seconds, face_distance),
            )

        # Har kunda 1-3 ta alert
        alert_count = random.randint(1, 3) if day_idx >= 2 else random.randint(0, 1)
        alert_issues = [
            '["Boshingizni ko\'taring!"]',
            '["Yelkalaringizni tekislang!"]',
            '["Oldinga engashmang!"]',
            '["Tanaffus qiling!"]',
            '["Ekranga yaqin!"]',
        ]
        for _ in range(alert_count):
            alert_time = current_date + timedelta(
                minutes=random.randint(30, 480)
            )
            cursor.execute(
                "INSERT INTO alerts (timestamp, issues) VALUES (?, ?)",
                (alert_time.isoformat(timespec="seconds"), random.choice(alert_issues)),
            )

        # Session yopish
        end_time = (current_date + timedelta(hours=random.randint(4, 8))).isoformat(
            timespec="seconds"
        )
        cursor.execute(
            "UPDATE sessions SET end_time = ? WHERE id = ?", (end_time, session_id)
        )

    conn.commit()
    conn.close()

    print("7 kunlik demo ma'lumotlar muvaffaqiyatli yaratildi!")
    print("Endi dasturni ishga tushiring: python main.py")
    print("Dashboard'da haftalik trend va Predictive Forecast ko'rinadi.")


if __name__ == "__main__":
    generate_mock_data()
