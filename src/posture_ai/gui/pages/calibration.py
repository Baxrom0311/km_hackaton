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
        self.setMinimumSize(760, 560)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(36, 36, 36, 36)
        main_layout.setSpacing(22)

        # Title
        lbl_title = QLabel("AI Kalibrovka")
        lbl_title.setObjectName("CalibrationTitle")
        lbl_title.setProperty("class", "TitleText")
        main_layout.addWidget(lbl_title, alignment=Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)

        # Card
        card = QFrame()
        card.setObjectName("CalibrationCard")
        card.setProperty("class", "GlassCard")
        card.setMinimumSize(640, 430)
        card.setMaximumWidth(820)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(42, 36, 42, 36)
        card_layout.setSpacing(18)

        lbl_desc = QLabel("Dastur sizning 'to'g'ri' o'tirish qaddingizni bilib olishi uchun, hozir kameraga qarab 12 soniya to'ppa-to'g'ri o'tirib turing.")
        lbl_desc.setObjectName("CalibrationDescription")
        lbl_desc.setWordWrap(True)
        lbl_desc.setMinimumWidth(560)
        lbl_desc.setMinimumHeight(86)
        lbl_desc.setProperty("class", "SubtitleText")
        lbl_desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(lbl_desc)

        lbl_tip = QLabel("Kompyuter kamerasi uchun: yuzingiz va ikkala yelkangiz kadrda aniq ko'rinsin.")
        lbl_tip.setObjectName("CalibrationTip")
        lbl_tip.setWordWrap(True)
        lbl_tip.setMinimumWidth(560)
        lbl_tip.setMinimumHeight(42)
        lbl_tip.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(lbl_tip)

        self.btn_start = QPushButton("Boshlash")
        self.btn_start.setObjectName("CalibrationButton")
        self.btn_start.setProperty("class", "CTAButton")
        self.btn_start.setMinimumSize(260, 54)
        self.btn_start.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_start.clicked.connect(self.start_calibration)
        card_layout.addWidget(self.btn_start, alignment=Qt.AlignmentFlag.AlignCenter)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setTextVisible(False)
        self.progress.setMinimumWidth(560)
        self.progress.setFixedHeight(22)
        self.progress.hide()
        card_layout.addWidget(self.progress)

        self.lbl_status = QLabel("")
        self.lbl_status.setObjectName("CalibrationStatus")
        self.lbl_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_status.setWordWrap(True)
        self.lbl_status.setMinimumWidth(560)
        self.lbl_status.setMinimumHeight(88)
        self.lbl_status.setProperty("class", "SubtitleText")
        card_layout.addWidget(self.lbl_status)

        main_layout.addWidget(card, alignment=Qt.AlignmentFlag.AlignHCenter)
        main_layout.addStretch()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_calibration_tick)

    def set_status(self, text: str, style_class: str = "HighlightCyan"):
        """Dynamic class o'zgarganda Qt stylesheetni qayta qo'llash."""
        self.lbl_status.setText(text)
        self.lbl_status.setProperty("class", style_class)
        self.lbl_status.style().unpolish(self.lbl_status)
        self.lbl_status.style().polish(self.lbl_status)
        self.lbl_status.update()

    def start_calibration(self):
        if self.is_calibrating:
            return
        self.is_calibrating = True
        self.samples = []
        self.time_left = self.config.calibration_seconds
        
        self.btn_start.hide()
        self.progress.show()
        self.progress.setValue(0)
        
        self.set_status(
            f"Tugashiga {self.time_left} soniya qoldi... To'g'ri o'tiring!\n"
            f"Namuna: 0/{self.config.calibration_min_samples}"
        )

        if hasattr(self.worker, "set_force_ai_sampling"):
            self.worker.set_force_ai_sampling(True)
        self.worker.metrics_updated.connect(self.collect_sample)
        self.timer.start(1000)

    def collect_sample(self, result):
        if not self.is_calibrating:
            return
        if not result.skipped and result.posture_score is not None and result.head_angle is not None:
            self.samples.append(result)

    def update_calibration_tick(self):
        self.time_left -= 1
        pct = int(((self.config.calibration_seconds - self.time_left) / self.config.calibration_seconds) * 100)
        self.progress.setValue(pct)
        self.set_status(
            f"Tugashiga {self.time_left} soniya qoldi... To'g'ri o'tiring!\n"
            f"Namuna: {len(self.samples)}/{self.config.calibration_min_samples}"
        )

        if self.time_left <= 0:
            self.finish_calibration()

    def finish_calibration(self):
        self.timer.stop()
        self.is_calibrating = False
        if hasattr(self.worker, "set_force_ai_sampling"):
            self.worker.set_force_ai_sampling(False)
        try:
            self.worker.metrics_updated.disconnect(self.collect_sample)
        except (RuntimeError, TypeError):
            pass

        if len(self.samples) < self.config.calibration_min_samples:
            self.set_status(
                f"Xatolik: sample yetarli emas ({len(self.samples)} / "
                f"{self.config.calibration_min_samples}). "
                "Kameraga to'liq ko'rinib qaytadan urinib ko'ring.",
                "WarningText",
            )
            self.btn_start.show()
            self.progress.hide()
            return

        import statistics
        head_baseline = statistics.median(s.head_angle for s in self.samples)
        shoulder_baseline = statistics.median(s.shoulder_diff for s in self.samples)
        forward_baseline = statistics.median(s.forward_lean for s in self.samples)
        roll_baseline = statistics.median(abs(getattr(s, "roll_xy_deg", 0.0) or 0.0) for s in self.samples)
        yaw_baseline = statistics.median(abs(getattr(s, "yaw_xz_deg", 0.0) or 0.0) for s in self.samples)
        pitch_baseline = statistics.median(abs(getattr(s, "pitch_yz_deg", 0.0) or 0.0) for s in self.samples)

        self.config.baseline_head_angle = head_baseline
        self.config.baseline_shoulder_diff = shoulder_baseline
        self.config.baseline_forward_lean = forward_baseline
        self.config.baseline_roll_xy_deg = roll_baseline
        self.config.baseline_yaw_xz_deg = yaw_baseline
        self.config.baseline_pitch_yz_deg = pitch_baseline

        self.config.head_angle_threshold = min(max(head_baseline + 8.0, 18.0), 35.0)
        self.config.shoulder_diff_threshold = min(max(shoulder_baseline + 0.02, 0.03), 0.12)
        self.config.forward_lean_threshold = max(min(forward_baseline - 0.12, -0.08), -0.40)
        self.config.roll_xy_threshold_deg = min(max(roll_baseline + 6.0, 8.0), 24.0)
        self.config.yaw_xz_threshold_deg = min(max(yaw_baseline + 8.0, 10.0), 30.0)
        self.config.pitch_yz_threshold_deg = min(max(pitch_baseline + 8.0, 10.0), 30.0)

        from posture_ai.core.config import save_config
        save_config(self.config)

        self.set_status(
            "Kalibrovka muvaffaqiyatli yakunlandi!\n"
            "3D shaxsiy profil va thresholdlar saqlandi.",
            "SuccessText",
        )

        self.btn_start.setText("Qayta Kalibrovka Qilish")
        self.btn_start.show()
        self.progress.hide()
