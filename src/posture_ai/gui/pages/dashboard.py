import cv2
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QFrame, QGridLayout, QProgressBar, QScrollArea
)
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtCore import Qt, QTimer

from posture_ai.core.forecast import forecast_risk
from posture_ai.core.exercises import recommend_exercises


class StatCard(QFrame):
    """Kichik statistik karta — raqam + sarlavha."""

    def __init__(self, title: str, value: str = "--", accent: str = "#00f5d4"):
        super().__init__()
        self.setProperty("class", "GlassCard")
        self.setFixedHeight(100)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(4)

        self.lbl_value = QLabel(value)
        self.lbl_value.setStyleSheet(f"font-size: 28px; font-weight: bold; color: {accent};")
        self.lbl_value.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.lbl_title = QLabel(title)
        self.lbl_title.setStyleSheet("font-size: 12px; color: #a0aabf;")
        self.lbl_title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(self.lbl_value)
        layout.addWidget(self.lbl_title)

    def set_value(self, text: str):
        self.lbl_value.setText(text)


class MiniBar(QFrame):
    """Haftalik mini-bar grafik uchun bitta kun ustuni."""

    def __init__(self, label: str = "", pct: float = 0.0):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 0, 2, 0)
        layout.setSpacing(2)

        self.bar = QProgressBar()
        self.bar.setOrientation(Qt.Orientation.Vertical)
        self.bar.setRange(0, 100)
        self.bar.setValue(int(pct))
        self.bar.setTextVisible(False)
        self.bar.setFixedWidth(28)
        self.bar.setMinimumHeight(60)
        self.bar.setStyleSheet("""
            QProgressBar { background-color: #1a0533; border: 1px solid rgba(123,97,255,0.2); border-radius: 4px; }
            QProgressBar::chunk { background-color: qlineargradient(x1:0,y1:1,x2:0,y2:0, stop:0 #7b61ff, stop:1 #00f5d4); border-radius: 3px; }
        """)

        self.lbl = QLabel(label)
        self.lbl.setStyleSheet("font-size: 10px; color: #a0aabf;")
        self.lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.lbl_pct = QLabel(f"{int(pct)}%")
        self.lbl_pct.setStyleSheet("font-size: 10px; color: #00f5d4;")
        self.lbl_pct.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(self.lbl_pct)
        layout.addWidget(self.bar, stretch=1)
        layout.addWidget(self.lbl)

    def update_bar(self, label: str, pct: float):
        self.bar.setValue(int(pct))
        self.lbl.setText(label)
        self.lbl_pct.setText(f"{int(pct)}%")


class DashboardPage(QWidget):
    def __init__(self, storage):
        super().__init__()
        self.storage = storage
        self.init_ui()

        # Auto-refresh today stats every 30 seconds
        self.stats_timer = QTimer(self)
        self.stats_timer.timeout.connect(self.refresh_today_stats)
        self.stats_timer.start(30_000)
        self.refresh_today_stats()

    def init_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(20)

        # ═══════ LEFT COLUMN: Camera Feed ═══════
        left_layout = QVBoxLayout()

        lbl_title = QLabel("Jonli Kuzatuv")
        lbl_title.setProperty("class", "TitleText")

        self.lbl_camera = QLabel("Kamera qidirilmoqda...")
        self.lbl_camera.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_camera.setMinimumSize(480, 360)
        self.lbl_camera.setStyleSheet(
            "background-color: #05070e; border: 2px solid #1a0533; border-radius: 12px;"
        )

        left_layout.addWidget(lbl_title)
        left_layout.addWidget(self.lbl_camera, stretch=1)

        # ═══════ RIGHT COLUMN ═══════
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(14)

        # ── Row 1: Ergonomic Score (katta) ──
        score_card = QFrame()
        score_card.setProperty("class", "GlassCard")
        score_inner = QVBoxLayout(score_card)
        score_inner.setContentsMargins(20, 16, 20, 16)
        score_inner.setSpacing(6)

        lbl_score_title = QLabel("Ergonomic Score")
        lbl_score_title.setProperty("class", "SubtitleText")

        self.lbl_score = QLabel("--")
        self.lbl_score.setStyleSheet("font-size: 48px; font-weight: bold; color: #00f5d4;")
        self.lbl_score.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.lbl_status = QLabel("Status: N/A")
        self.lbl_status.setProperty("class", "SubtitleText")
        self.lbl_status.setAlignment(Qt.AlignmentFlag.AlignCenter)

        score_inner.addWidget(lbl_score_title)
        score_inner.addWidget(self.lbl_score)
        score_inner.addWidget(self.lbl_status)

        # ── Row 2: Real-time metric cards (4 ta) ──
        metrics_row = QHBoxLayout()
        metrics_row.setSpacing(10)

        self.card_head = StatCard("Bosh burchagi", "--°", "#00f5d4")
        self.card_shoulder = StatCard("Yelka farqi", "--", "#7b61ff")
        self.card_lean = StatCard("Engashish", "--", "#00f5d4")
        self.card_sit = StatCard("O'tirish", "0 daq", "#ff9f43")

        metrics_row.addWidget(self.card_head)
        metrics_row.addWidget(self.card_shoulder)
        metrics_row.addWidget(self.card_lean)
        metrics_row.addWidget(self.card_sit)

        # ── Row 3: Bugungi statistika ──
        today_card = QFrame()
        today_card.setProperty("class", "GlassCard")
        today_inner = QVBoxLayout(today_card)
        today_inner.setContentsMargins(16, 12, 16, 12)
        today_inner.setSpacing(8)

        lbl_today = QLabel("Bugungi Statistika")
        lbl_today.setProperty("class", "SubtitleText")

        self.today_grid = QGridLayout()
        self.today_grid.setSpacing(8)

        self.lbl_good_pct = QLabel("To'g'ri: --%")
        self.lbl_good_pct.setStyleSheet("color: #00f5d4; font-size: 14px; font-weight: bold;")
        self.lbl_bad_pct = QLabel("Noto'g'ri: --%")
        self.lbl_bad_pct.setStyleSheet("color: #ff4d4f; font-size: 14px; font-weight: bold;")
        self.lbl_alerts = QLabel("Ogohlantirishlar: 0")
        self.lbl_alerts.setStyleSheet("color: #ff9f43; font-size: 14px;")
        self.lbl_avg_ergo = QLabel("O'rtacha: --")
        self.lbl_avg_ergo.setStyleSheet("color: #7b61ff; font-size: 14px;")

        self.today_grid.addWidget(self.lbl_good_pct, 0, 0)
        self.today_grid.addWidget(self.lbl_bad_pct, 0, 1)
        self.today_grid.addWidget(self.lbl_alerts, 1, 0)
        self.today_grid.addWidget(self.lbl_avg_ergo, 1, 1)

        today_inner.addWidget(lbl_today)
        today_inner.addLayout(self.today_grid)

        # ── Row 4: Haftalik mini-grafik ──
        weekly_card = QFrame()
        weekly_card.setProperty("class", "GlassCard")
        weekly_inner = QVBoxLayout(weekly_card)
        weekly_inner.setContentsMargins(16, 12, 16, 12)
        weekly_inner.setSpacing(8)

        lbl_weekly = QLabel("Haftalik Trend")
        lbl_weekly.setProperty("class", "SubtitleText")

        self.weekly_bars_layout = QHBoxLayout()
        self.weekly_bars_layout.setSpacing(4)
        self.weekly_bars: list[MiniBar] = []
        for i in range(7):
            bar = MiniBar(f"K{i+1}", 0)
            self.weekly_bars.append(bar)
            self.weekly_bars_layout.addWidget(bar)

        weekly_inner.addWidget(lbl_weekly)
        weekly_inner.addLayout(self.weekly_bars_layout)

        # ── Row 5: Predictive Forecast ──
        forecast_card = QFrame()
        forecast_card.setProperty("class", "GlassCard")
        forecast_inner = QVBoxLayout(forecast_card)
        forecast_inner.setContentsMargins(16, 12, 16, 12)
        forecast_inner.setSpacing(8)

        lbl_forecast_title = QLabel("Predictive Forecast")
        lbl_forecast_title.setProperty("class", "TitleText")
        lbl_forecast_title.setStyleSheet("font-size: 18px; font-weight: bold; color: #ffffff;")

        self.lbl_forecast = QLabel("Ma'lumot yig'ilmoqda...\nHech bo'lmaganda 2 kunlik tarix kerak.")
        self.lbl_forecast.setWordWrap(True)
        self.lbl_forecast.setProperty("class", "SubtitleText")

        forecast_inner.addWidget(lbl_forecast_title)
        forecast_inner.addWidget(self.lbl_forecast)

        # ── Row 6: Mashq Tavsiyalari ──
        exercise_card = QFrame()
        exercise_card.setProperty("class", "GlassCard")
        exercise_inner = QVBoxLayout(exercise_card)
        exercise_inner.setContentsMargins(16, 12, 16, 12)
        exercise_inner.setSpacing(8)

        lbl_exercise_title = QLabel("Shaxsiy Mashq Tavsiyalari")
        lbl_exercise_title.setStyleSheet("font-size: 18px; font-weight: bold; color: #ffffff;")

        self.lbl_exercises = QLabel("Ma'lumot yig'ilmoqda...")
        self.lbl_exercises.setWordWrap(True)
        self.lbl_exercises.setProperty("class", "SubtitleText")

        exercise_inner.addWidget(lbl_exercise_title)
        exercise_inner.addWidget(self.lbl_exercises)

        # ── Assemble right column ──
        right_layout.addWidget(score_card)
        right_layout.addLayout(metrics_row)
        right_layout.addWidget(today_card)
        right_layout.addWidget(weekly_card)
        right_layout.addWidget(forecast_card)
        right_layout.addWidget(exercise_card)
        right_layout.addStretch()

        # Scrollable right side
        scroll = QScrollArea()
        scroll.setWidget(right_widget)
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        main_layout.addLayout(left_layout, stretch=2)
        main_layout.addWidget(scroll, stretch=1)

    # ── Real-time updates from CameraWorker ──

    def update_metrics(self, result):
        # Score
        self.lbl_score.setText(str(result.ergonomic_score or "--"))

        if result.status == "good":
            self.lbl_score.setStyleSheet("font-size: 48px; font-weight: bold; color: #00f5d4;")
            self.lbl_status.setText("Status: GOOD")
            self.lbl_status.setProperty("class", "SuccessText")
        else:
            self.lbl_score.setStyleSheet("font-size: 48px; font-weight: bold; color: #ff4d4f;")
            self.lbl_status.setText("Status: BAD")
            self.lbl_status.setProperty("class", "WarningText")
        self.lbl_status.style().unpolish(self.lbl_status)
        self.lbl_status.style().polish(self.lbl_status)

        # Metric cards
        self.card_head.set_value(f"{result.head_angle or '--'}°")
        self.card_shoulder.set_value(f"{result.shoulder_diff or '--'}")
        self.card_lean.set_value(f"{result.forward_lean or '--'}")

        sit_min = result.sit_seconds / 60.0
        if sit_min >= 20:
            self.card_sit.lbl_value.setStyleSheet("font-size: 28px; font-weight: bold; color: #ff4d4f;")
        elif sit_min >= 10:
            self.card_sit.lbl_value.setStyleSheet("font-size: 28px; font-weight: bold; color: #ff9f43;")
        else:
            self.card_sit.lbl_value.setStyleSheet("font-size: 28px; font-weight: bold; color: #00f5d4;")
        self.card_sit.set_value(f"{sit_min:.0f} daq")

    def update_frame(self, frame):
        if frame is None:
            return
        try:
            import numpy as np
            rgb_image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            h, w, ch = rgb_image.shape

            # Markazdan crop — faqat yuz va yelkalar ko'rinadi
            crop_ratio = 0.75
            crop_h = int(h * crop_ratio)
            crop_w = int(w * crop_ratio)
            y_start = (h - crop_h) // 2
            x_start = (w - crop_w) // 2
            rgb_image = np.ascontiguousarray(rgb_image[y_start:y_start + crop_h, x_start:x_start + crop_w])
            h, w, ch = rgb_image.shape

            bytes_per_line = ch * w
            q_img = QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
            pixmap = QPixmap.fromImage(q_img)
            self.lbl_camera.setPixmap(
                pixmap.scaled(
                    self.lbl_camera.width(),
                    self.lbl_camera.height(),
                    Qt.AspectRatioMode.KeepAspectRatio,
                )
            )
        except Exception:
            pass

    # ── Periodic stats refresh ──

    def refresh_today_stats(self):
        stats = self.storage.get_today_stats()
        self.lbl_good_pct.setText(f"To'g'ri: {stats['good_pct']}%")
        self.lbl_bad_pct.setText(f"Noto'g'ri: {stats['bad_pct']}%")
        self.lbl_alerts.setText(f"Ogohlantirishlar: {stats['alerts_count']}")
        self.lbl_avg_ergo.setText(f"O'rtacha: {stats['avg_ergonomic']}")

        self._update_weekly_bars()
        self._update_exercises()

    def _update_weekly_bars(self):
        weekly = self.storage.get_weekly_summary()
        day_names = ["Du", "Se", "Ch", "Pa", "Ju", "Sh", "Ya"]
        for i, bar in enumerate(self.weekly_bars):
            if i < len(weekly):
                row = weekly[i]
                day_str = row.get("day", "")
                short = day_str[-2:] if day_str else f"K{i+1}"
                pct = row.get("good_pct", 0)
                bar.update_bar(short, pct)
            else:
                bar.update_bar("--", 0)

    def _update_exercises(self):
        frequent = self.storage.get_today_frequent_issues()
        if not frequent:
            self.lbl_exercises.setText(
                "<span style='color:#a0aabf;'>Hali muammolar aniqlanmagan. "
                "Mashqlar avtomatik ravishda tavsiya qilinadi.</span>"
            )
            return

        exercises = recommend_exercises(frequent, max_exercises=3)
        if not exercises:
            return

        html_parts = []
        for i, ex in enumerate(exercises, 1):
            html_parts.append(
                f"<div style='margin-bottom:8px;'>"
                f"<span style='color:#00f5d4; font-weight:bold;'>{i}. {ex.name}</span>"
                f" <span style='color:#7b61ff;'>({ex.duration_sec} sek)</span><br>"
                f"<span style='color:#d0d0d0;'>{ex.description}</span><br>"
                f"<span style='color:#ff9f43; font-size:12px;'>Foyda: {ex.benefit}</span>"
                f"</div>"
            )
        self.lbl_exercises.setText("".join(html_parts))

    # ── Forecast ──

    def update_forecast(self):
        weekly = self.storage.get_weekly_summary()
        forecast = forecast_risk(weekly)
        if forecast:
            color = "#00f5d4" if forecast.category in ("low",) else "#ff9f43" if forecast.category == "moderate" else "#ff4d4f"
            msg = (
                f"<span style='color:{color}; font-size:20px; font-weight:bold;'>"
                f"30 kunlik Og'riq Ehtimoli: {forecast.pain_probability_30d * 100:.0f}%</span><br><br>"
                f"Hozirgi xavf: <b>{forecast.current_risk:.0f}</b>/100 &nbsp;|&nbsp; "
                f"7 kunlik prognoz: <b>{forecast.projected_risk_7d:.0f}</b>/100<br>"
                f"Trend: <b>{forecast.slope_per_day:+.2f}</b> /kun<br><br>"
                f"<span style='color:#7b61ff; font-weight:bold;'>Tavsiya:</span><br>"
                f"{forecast.recommendation}"
            )
            self.lbl_forecast.setText(msg)
        else:
            self.lbl_forecast.setText(
                "Ma'lumot yig'ilmoqda...\nHech bo'lmaganda 2 kunlik tarix kerak."
            )
