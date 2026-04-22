from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QFrame, QGridLayout, QProgressBar, QScrollArea,
    QPushButton, QFileDialog, QMessageBox
)
from PySide6.QtGui import QPainter, QPen, QColor, QFont, QTextDocument
from PySide6.QtCore import Qt, QTimer, QRectF
import datetime

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


class CircularGauge(QWidget):
    """Doiraviy Gauge (Speedometer) vidjeti."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(220, 220)
        self.value = 0
        self.status_text = "Kuzatilmoqda..."

    def set_value(self, val: int, status: str):
        self.value = val
        self.status_text = status
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        size = min(self.width(), self.height())
        rect = QRectF(self.width() / 2 - size / 2 + 15, self.height() / 2 - size / 2 + 15, size - 30, size - 30)

        # Background arc
        pen_bg = QPen(QColor("#1a0533"), 14)
        pen_bg.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen_bg)
        start_angle = 225 * 16
        span_angle = -270 * 16
        painter.drawArc(rect, start_angle, span_angle)

        # Rang tanlash
        if self.value >= 80:
            color = QColor("#00f5d4")  # Yashil (Good)
        elif self.value >= 50:
            color = QColor("#ff9f43")  # Sariq (Warning)
        elif self.value > 0:
            color = QColor("#ff4d4f")  # Qizil (Bad)
        else:
            color = QColor("#a0aabf")  # Kulrang (0 yoki unknown)

        # Progress arc
        pen_fg = QPen(color, 14)
        pen_fg.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen_fg)
        val_span = int(-270 * 16 * (self.value / 100.0))
        painter.drawArc(rect, start_angle, val_span)

        # Markazdagi matn (Qiymat)
        painter.setPen(color)
        font_score = QFont("Arial", 48, QFont.Weight.Bold)
        painter.setFont(font_score)
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, str(self.value) if self.value > 0 else "--")

        # Pastki matn (Status)
        painter.setPen(QColor("#a0aabf"))
        font_status = QFont("Arial", 12)
        painter.setFont(font_status)
        text_rect = self.rect().adjusted(0, 80, 0, 0)
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, self.status_text)


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
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(16)

        lbl_title = QLabel("Analiz")
        lbl_title.setProperty("class", "TitleText")
        main_layout.addWidget(lbl_title)

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

        lbl_score_title = QLabel("Umumiy Ergonomik Ball")
        lbl_score_title.setProperty("class", "SubtitleText")
        lbl_score_title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.gauge = CircularGauge()

        score_inner.addWidget(lbl_score_title)
        score_inner.addWidget(self.gauge, alignment=Qt.AlignmentFlag.AlignCenter)

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

        # ── Row 2b: Yangi metrik kartalar ──
        metrics_row2 = QHBoxLayout()
        metrics_row2.setSpacing(10)

        self.card_xy = StatCard("XY burchak", "--°", "#7b61ff")
        self.card_xz = StatCard("XZ burchak", "--°", "#ff9f43")
        self.card_yz = StatCard("YZ burchak", "--°", "#00f5d4")
        self.card_fatigue = StatCard("Charchoq", "--", "#00f5d4")
        metrics_row2.addWidget(self.card_xy)
        metrics_row2.addWidget(self.card_xz)
        metrics_row2.addWidget(self.card_yz)
        metrics_row2.addWidget(self.card_fatigue)

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

        self.btn_export_pdf = QPushButton("📥 Hisobotni PDF ga saqlash")
        self.btn_export_pdf.setStyleSheet("""
            QPushButton {
                background-color: rgba(123, 97, 255, 0.2);
                border: 1px solid rgba(123, 97, 255, 0.5);
                border-radius: 6px;
                color: #ffffff;
                padding: 6px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: rgba(123, 97, 255, 0.4);
            }
        """)
        self.btn_export_pdf.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_export_pdf.clicked.connect(self.export_pdf)

        today_inner.addWidget(lbl_today)
        today_inner.addLayout(self.today_grid)
        today_inner.addWidget(self.btn_export_pdf)

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
        right_layout.addLayout(metrics_row2)
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

        main_layout.addWidget(scroll, stretch=1)

    # ── Real-time updates from CameraWorker ──

    def update_metrics(self, result):
        # Umumiy Ball (Gauge)
        val = result.ergonomic_score or 0
        if result.status == "good":
            status_text = "YAXSHI ✓"
        elif result.skipped:
            status_text = "Kuzatilmoqda..."
        else:
            issues_text = ", ".join(result.issues[:2]) if result.issues else "NOTO'G'RI"
            status_text = f"⚠ {issues_text}"
            
        self.gauge.set_value(val, status_text)

        # Metric cards — asosiy
        self.card_head.set_value(f"{result.head_angle or '--'}°")
        self.card_shoulder.set_value(f"{result.shoulder_diff or '--'}")
        self.card_lean.set_value(f"{result.forward_lean or '--'}")

        # Yangi metrik kartalar
        xy_angle = getattr(result, 'roll_xy_deg', None)
        self.card_xy.set_value(f"{xy_angle:+.1f}°" if xy_angle is not None else "--°")
        if xy_angle is not None and abs(xy_angle) > 12.0:
            self.card_xy.lbl_value.setStyleSheet("font-size: 28px; font-weight: bold; color: #ff4d4f;")
        else:
            self.card_xy.lbl_value.setStyleSheet("font-size: 28px; font-weight: bold; color: #7b61ff;")

        xz_angle = getattr(result, 'yaw_xz_deg', None)
        self.card_xz.set_value(f"{xz_angle:+.1f}°" if xz_angle is not None else "--°")
        if xz_angle is not None and abs(xz_angle) > 18.0:
            self.card_xz.lbl_value.setStyleSheet("font-size: 28px; font-weight: bold; color: #ff4d4f;")
        else:
            self.card_xz.lbl_value.setStyleSheet("font-size: 28px; font-weight: bold; color: #ff9f43;")

        yz_angle = getattr(result, 'pitch_yz_deg', None)
        self.card_yz.set_value(f"{yz_angle:+.1f}°" if yz_angle is not None else "--°")
        if yz_angle is not None and abs(yz_angle) > 18.0:
            self.card_yz.lbl_value.setStyleSheet("font-size: 28px; font-weight: bold; color: #ff4d4f;")
        else:
            self.card_yz.lbl_value.setStyleSheet("font-size: 28px; font-weight: bold; color: #00f5d4;")

        sit_min = result.sit_seconds / 60.0
        if sit_min >= 20:
            self.card_sit.lbl_value.setStyleSheet("font-size: 28px; font-weight: bold; color: #ff4d4f;")
        elif sit_min >= 10:
            self.card_sit.lbl_value.setStyleSheet("font-size: 28px; font-weight: bold; color: #ff9f43;")
        else:
            self.card_sit.lbl_value.setStyleSheet("font-size: 28px; font-weight: bold; color: #00f5d4;")
        self.card_sit.set_value(f"{sit_min:.0f} daq")

        fatigue_score = getattr(result, "fatigue_score", None)
        fatigue_level = getattr(result, "fatigue_level", None)
        if fatigue_score is None:
            self.card_fatigue.set_value("--")
            self.card_fatigue.lbl_value.setStyleSheet("font-size: 28px; font-weight: bold; color: #a0aabf;")
        else:
            if fatigue_level == "high":
                label, color = "Yuqori", "#ff4d4f"
            elif fatigue_level == "moderate":
                label, color = "O'rta", "#ff9f43"
            else:
                label, color = "Past", "#00f5d4"
            self.card_fatigue.set_value(f"{label} {fatigue_score}")
            self.card_fatigue.lbl_value.setStyleSheet(f"font-size: 24px; font-weight: bold; color: {color};")

    # ── Periodic stats refresh ──

    def export_pdf(self):
        try:
            from PySide6.QtPrintSupport import QPrinter
        except ImportError:
            QMessageBox.warning(self, "Xatolik", "PDF eksport qilish uchun QtPrintSupport moduli yetishmayapti.")
            return

        file_path, _ = QFileDialog.getSaveFileName(self, "PDF hisobotni saqlash", "PostureAI_Hisobot.pdf", "PDF Files (*.pdf)")
        if not file_path:
            return

        today = datetime.date.today().isoformat()
        stats = self.storage.get_today_stats()
        weekly = self.storage.get_weekly_summary()
        forecast = forecast_risk(weekly)
        frequent = self.storage.get_today_frequent_issues()
        exercises = recommend_exercises(frequent, max_exercises=3) if frequent else []

        # Haftalik jadval
        weekly_rows = ""
        for row in weekly:
            weekly_rows += (
                f"<tr><td>{row['day']}</td>"
                f"<td class='good'>{row['good_pct']}%</td>"
                f"<td>{row['avg_score']:.1f}</td>"
                f"<td>{row['avg_ergonomic']:.1f}</td>"
                f"<td class='highlight'>{row['bad_count']}</td></tr>"
            )

        # Forecast blok
        forecast_html = "<p>Ma'lumot yetarli emas (kamida 2 kunlik tarix kerak).</p>"
        if forecast:
            cat_color = "#27ae60" if forecast.category == "low" else "#e67e22" if forecast.category == "moderate" else "#e74c3c"
            forecast_html = f"""
            <table>
                <tr><th>Hozirgi xavf darajasi</th><td><b style="color:{cat_color};">{forecast.current_risk:.0f}/100 ({forecast.category})</b></td></tr>
                <tr><th>7 kunlik prognoz</th><td>{forecast.projected_risk_7d:.0f}/100 (80% CI: {forecast.confidence_lower:.0f}–{forecast.confidence_upper:.0f})</td></tr>
                <tr><th>Kunlik trend</th><td>{forecast.slope_per_day:+.2f} /kun</td></tr>
                <tr><th>30 kunlik og'riq ehtimoli</th><td><b style="color:{cat_color};">{forecast.pain_probability_30d * 100:.0f}%</b></td></tr>
                <tr><th>Model aniqligi</th><td>R²={forecast.r_squared:.3f} | MAPE={forecast.mape:.1f}%</td></tr>
                <tr><th>Model</th><td>{forecast.model_used}</td></tr>
            </table>
            <p><b>Tavsiya:</b> {forecast.recommendation}</p>
            """

        # Mashqlar blok
        exercises_html = ""
        if exercises:
            exercises_html = "<h2>Tavsiya Etilgan Mashqlar</h2><ol>"
            for ex in exercises:
                exercises_html += (
                    f"<li><b>{ex.name}</b> ({ex.duration_sec} sek) — {ex.target}<br>"
                    f"<span style='color:#555;'>{ex.description}</span><br>"
                    f"<span style='color:#2980b9;'>Foyda: {ex.benefit}</span></li><br>"
                )
            exercises_html += "</ol>"

        # Ko'p uchraydigan muammolar
        issues_html = ""
        if frequent:
            issues_html = "<h2>Ko'p Uchraydigan Muammolar</h2><table>"
            issues_html += "<tr><th>Muammo</th><th>Soni</th></tr>"
            for issue, count in frequent[:5]:
                issues_html += f"<tr><td>{issue}</td><td>{count}</td></tr>"
            issues_html += "</table>"

        html = f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; color: #333; }}
                h1 {{ color: #2c3e50; text-align: center; border-bottom: 2px solid #3498db; padding-bottom: 10px; }}
                h2 {{ color: #2980b9; margin-top: 20px; }}
                table {{ width: 100%; border-collapse: collapse; margin-top: 10px; }}
                th, td {{ border: 1px solid #bdc3c7; padding: 10px; text-align: left; }}
                th {{ background-color: #ecf0f1; width: 40%; }}
                .highlight {{ font-weight: bold; color: #e74c3c; }}
                .good {{ color: #27ae60; font-weight: bold; }}
                .section {{ page-break-inside: avoid; }}
            </style>
        </head>
        <body>
            <h1>PostureAI Ergonomik Hisobot</h1>
            <p style="text-align: right;">Sana: <b>{today}</b></p>

            <div class="section">
            <h2>Bugungi Statistika</h2>
            <table>
                <tr><th>O'rtacha Ergonomik Ball</th><td><b style="font-size: 16px;">{stats['avg_ergonomic']} / 100</b></td></tr>
                <tr><th>O'rtacha Posture Ball</th><td>{stats['avg_score']} / 100</td></tr>
                <tr><th>To'g'ri Holat</th><td class="good">{stats['good_pct']}%</td></tr>
                <tr><th>Noto'g'ri Holat</th><td class="highlight">{stats['bad_pct']}%</td></tr>
                <tr><th>Ogohlantirishlar</th><td>{stats['alerts_count']} ta</td></tr>
                <tr><th>Jami namunalar</th><td>{stats['total_samples']}</td></tr>
                <tr><th>Max uzluksiz o'tirish</th><td>{stats['max_sit_seconds'] / 60.0:.1f} daqiqa</td></tr>
            </table>
            </div>

            <div class="section">
            <h2>Haftalik Trend</h2>
            <table>
                <tr><th>Kun</th><th>To'g'ri %</th><th>Posture</th><th>Ergonomik</th><th>Xatolar</th></tr>
                {weekly_rows if weekly_rows else "<tr><td colspan='5'>Ma'lumot yo'q</td></tr>"}
            </table>
            </div>

            <div class="section">
            <h2>Prediktiv Prognoz (Ensemble ML)</h2>
            {forecast_html}
            </div>

            {issues_html}
            {exercises_html}

            <br><hr>
            <p style="text-align: center; color: #7f8c8d; font-size: 11px;">
                PostureAI v2.0 — AI HEALTH 2026 | Ensemble Model: Linear + Holt Exp.Smoothing + WMA
            </p>
        </body>
        </html>
        """

        document = QTextDocument()
        document.setHtml(html)

        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
        printer.setOutputFileName(file_path)
        from PySide6.QtCore import QMarginsF
        printer.setPageMargins(QMarginsF(15, 15, 15, 15))

        document.print_(printer)

        QMessageBox.information(self, "Muvaffaqiyatli", f"Hisobot PDF formatida saqlandi:\n{file_path}")

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
                f"7 kunlik prognoz: <b>{forecast.projected_risk_7d:.0f}</b>/100 "
                f"<span style='color:#a0aabf;'>({forecast.confidence_lower:.0f}–{forecast.confidence_upper:.0f} CI)</span><br>"
                f"Trend: <b>{forecast.slope_per_day:+.2f}</b> /kun &nbsp;|&nbsp; "
                f"R²={forecast.r_squared:.2f} &nbsp;|&nbsp; MAPE={forecast.mape:.1f}%<br><br>"
                f"<span style='color:#7b61ff; font-weight:bold;'>Tavsiya:</span><br>"
                f"{forecast.recommendation}"
            )
            self.lbl_forecast.setText(msg)
        else:
            self.lbl_forecast.setText(
                "Ma'lumot yig'ilmoqda...\nHech bo'lmaganda 2 kunlik tarix kerak."
            )
