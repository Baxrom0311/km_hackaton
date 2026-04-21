from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QFrame, QPushButton, QProgressBar, QMessageBox
)
from PySide6.QtCore import Qt, QTimer
# from posture_ai.core.config import save_config

class CalibrationPage(QWidget):
    def __init__(self, config, worker):
        super().__init__()
        self.config = config
        self.worker = worker
        self.is_calibrating = False
        self.samples = []
        self.time_left = 0
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(50, 50, 50, 50)
        main_layout.setSpacing(20)

        # Title
        lbl_title = QLabel("AI Kalibrovka")
        lbl_title.setProperty("class", "TitleText")
        main_layout.addWidget(lbl_title, alignment=Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)

        # Card
        card = QFrame()
        card.setProperty("class", "GlassCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(40, 40, 40, 40)
        card_layout.setSpacing(20)

        lbl_desc = QLabel("Dastur sizning 'to'g'ri' o'tirish qaddingizni bilib olishi uchun, hozir kameraga qarab 12 soniya to'ppa-to'g'ri o'tirib turing.")
        lbl_desc.setWordWrap(True)
        lbl_desc.setProperty("class", "SubtitleText")
        lbl_desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(lbl_desc)

        self.btn_start = QPushButton("Boshlash")
        self.btn_start.setProperty("class", "CTAButton")
        self.btn_start.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_start.clicked.connect(self.start_calibration)
        card_layout.addWidget(self.btn_start)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(15)
        self.progress.hide()
        card_layout.addWidget(self.progress)

        self.lbl_status = QLabel("")
        self.lbl_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_status.setProperty("class", "SubtitleText")
        card_layout.addWidget(self.lbl_status)

        main_layout.addWidget(card, alignment=Qt.AlignmentFlag.AlignCenter)
        main_layout.addStretch()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_calibration_tick)

    def start_calibration(self):
        self.is_calibrating = True
        self.samples = []
        self.time_left = self.config.calibration_seconds
        
        self.btn_start.hide()
        self.progress.show()
        self.progress.setValue(0)
        
        self.lbl_status.setText(f"Tugashiga {self.time_left} soniya qoldi... To'g'ri o'tiring!")
        self.lbl_status.setProperty("class", "HighlightCyan")
        self.lbl_status.style().unpolish(self.lbl_status)
        self.lbl_status.style().polish(self.lbl_status)

        self.worker.metrics_updated.connect(self.collect_sample)
        self.timer.start(1000)

    def collect_sample(self, result):
        if not self.is_calibrating:
            return
        if result.head_angle is not None:
            self.samples.append(result)

    def update_calibration_tick(self):
        self.time_left -= 1
        pct = int(((self.config.calibration_seconds - self.time_left) / self.config.calibration_seconds) * 100)
        self.progress.setValue(pct)
        self.lbl_status.setText(f"Tugashiga {self.time_left} soniya qoldi... To'g'ri o'tiring!")

        if self.time_left <= 0:
            self.finish_calibration()

    def finish_calibration(self):
        self.timer.stop()
        self.is_calibrating = False
        try:
            self.worker.metrics_updated.disconnect(self.collect_sample)
        except (RuntimeError, TypeError):
            pass

        if len(self.samples) < self.config.calibration_min_samples:
            self.lbl_status.setText("Xatolik: Siz kameraga ko'rinmadingiz (ma'lumot yetarli emas). Qaytadan urinib ko'ring.")
            self.lbl_status.setProperty("class", "WarningText")
            self.btn_start.show()
            self.progress.hide()
            return

        # Calculate baselines manually since PostureResult doesn't have calculate directly
        import statistics
        head_baseline = statistics.median(s.head_angle for s in self.samples)
        shoulder_baseline = statistics.median(s.shoulder_diff for s in self.samples)
        forward_baseline = statistics.median(s.forward_lean for s in self.samples)

        # Update config directly in memory -> Save needs to happen via main_window or config
        self.config.baseline_head_angle = head_baseline
        self.config.baseline_shoulder_diff = shoulder_baseline
        self.config.baseline_forward_lean = forward_baseline

        from posture_ai.core.config import save_config
        save_config(self.config)

        self.lbl_status.setText("Kalibrovka muvaffaqiyatli yakunlandi! Shaxsiy profillaringiz xotiraga yozildi.")
        self.lbl_status.setProperty("class", "SuccessText")
        self.lbl_status.style().unpolish(self.lbl_status)
        self.lbl_status.style().polish(self.lbl_status)

        self.btn_start.setText("Qayta Kalibrovka Qilish")
        self.btn_start.show()
        self.progress.hide()
