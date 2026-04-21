from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QFrame, QPushButton, QFormLayout, QSpinBox, QMessageBox, QCheckBox,
)
from PySide6.QtCore import Qt

from posture_ai.core.config import save_config
from posture_ai.os_utils.autostart import is_autostart_enabled, enable_autostart, disable_autostart


class SettingsPage(QWidget):
    def __init__(self, config):
        super().__init__()
        self.config = config
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(50, 40, 50, 40)
        main_layout.setSpacing(20)

        # Title
        lbl_title = QLabel("Tizim Sozlamalari")
        lbl_title.setProperty("class", "TitleText")
        main_layout.addWidget(lbl_title, alignment=Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)

        # Settings Card
        card = QFrame()
        card.setProperty("class", "GlassCard")
        form_layout = QFormLayout(card)
        form_layout.setContentsMargins(40, 40, 40, 40)
        form_layout.setSpacing(15)
        form_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        spin_style = "background-color: #1a0533; color: white; padding: 5px; border-radius: 4px;"

        # Fields
        self.spin_camera = QSpinBox()
        self.spin_camera.setRange(0, 10)
        self.spin_camera.setValue(self.config.camera_index)
        self.spin_camera.setStyleSheet(spin_style)

        self.spin_fps = QSpinBox()
        self.spin_fps.setRange(1, 30)
        self.spin_fps.setValue(self.config.fps)
        self.spin_fps.setStyleSheet(spin_style)

        self.spin_window = QSpinBox()
        self.spin_window.setRange(10, 300)
        self.spin_window.setValue(self.config.temporal_window_size)
        self.spin_window.setStyleSheet(spin_style)

        self.spin_cooldown = QSpinBox()
        self.spin_cooldown.setRange(5, 600)
        self.spin_cooldown.setValue(self.config.cooldown_seconds)
        self.spin_cooldown.setSuffix(" sek")
        self.spin_cooldown.setStyleSheet(spin_style)

        self.spin_break = QSpinBox()
        self.spin_break.setRange(30, 7200)
        self.spin_break.setValue(self.config.sit_alert_threshold_seconds)
        self.spin_break.setSuffix(" sek")
        self.spin_break.setStyleSheet(spin_style)

        self.spin_ai_skip = QSpinBox()
        self.spin_ai_skip.setRange(1, 10)
        self.spin_ai_skip.setValue(self.config.ai_skip_frames)
        self.spin_ai_skip.setStyleSheet(spin_style)

        self.chk_autostart = QCheckBox("Kompyuter yoqilganda avtomatik ishga tushsin")
        self.chk_autostart.setChecked(is_autostart_enabled())
        self.chk_autostart.setStyleSheet("color: white; padding: 5px;")

        self.chk_minimized = QCheckBox("Orqa fon rejimida ishga tushsin (oyna ko'rsatilmaydi)")
        self.chk_minimized.setChecked(self.config.start_minimized)
        self.chk_minimized.setStyleSheet("color: white; padding: 5px;")

        form_layout.addRow(self.create_label("Kamera indeksi:"), self.spin_camera)
        form_layout.addRow(self.create_label("FPS (kadr/sek):"), self.spin_fps)
        form_layout.addRow(self.create_label("Temporal window:"), self.spin_window)
        form_layout.addRow(self.create_label("Alert orasidagi vaqt:"), self.spin_cooldown)
        form_layout.addRow(self.create_label("Tanaffus eslatmasi:"), self.spin_break)
        form_layout.addRow(self.create_label("AI skip frames:"), self.spin_ai_skip)
        form_layout.addRow("", self.chk_autostart)
        form_layout.addRow("", self.chk_minimized)

        main_layout.addWidget(card, alignment=Qt.AlignmentFlag.AlignCenter)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.btn_save = QPushButton("Saqlash")
        self.btn_save.setProperty("class", "CTAButton")
        self.btn_save.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_save.clicked.connect(self.save_settings)
        btn_layout.addWidget(self.btn_save)

        self.btn_reset = QPushButton("Qaytarish")
        self.btn_reset.setProperty("class", "CTAButton_Secondary")
        self.btn_reset.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_reset.clicked.connect(self.reset_to_default)
        btn_layout.addWidget(self.btn_reset)

        main_layout.addLayout(btn_layout)
        main_layout.addStretch()

    def create_label(self, text):
        lbl = QLabel(text)
        lbl.setProperty("class", "SubtitleText")
        return lbl

    def save_settings(self):
        self.config.camera_index = self.spin_camera.value()
        self.config.fps = self.spin_fps.value()
        self.config.temporal_window_size = self.spin_window.value()
        self.config.cooldown_seconds = self.spin_cooldown.value()
        self.config.sit_alert_threshold_seconds = self.spin_break.value()
        self.config.ai_skip_frames = self.spin_ai_skip.value()
        self.config.start_minimized = self.chk_minimized.isChecked()

        # Autostart
        if self.chk_autostart.isChecked():
            enable_autostart()
        else:
            disable_autostart()

        try:
            save_config(self.config)
            QMessageBox.information(
                self, "Muvaffaqiyatli",
                "Sozlamalar saqlandi!\nBa'zi o'zgarishlar dastur qayta ishga tushganda faollashadi."
            )
        except Exception as e:
            QMessageBox.warning(self, "Xato", f"Saqlashda muammo:\n{e}")

    def reset_to_default(self):
        reply = QMessageBox.question(
            self, "Tasdiqlash",
            "Barcha sozlamalar standart qiymatlarga qaytarilsinmi?\n"
            "Kalibrovka natijalari saqlanib qoladi.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        from posture_ai.core.config import AppConfig
        defaults = AppConfig()
        self.spin_camera.setValue(defaults.camera_index)
        self.spin_fps.setValue(defaults.fps)
        self.spin_window.setValue(defaults.temporal_window_size)
        self.spin_cooldown.setValue(defaults.cooldown_seconds)
        self.spin_break.setValue(defaults.sit_alert_threshold_seconds)
        self.spin_ai_skip.setValue(defaults.ai_skip_frames)
        self.chk_minimized.setChecked(defaults.start_minimized)
