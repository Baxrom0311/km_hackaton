from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QFrame, QPushButton, QLineEdit, QFormLayout, QSpinBox, QDoubleSpinBox, QMessageBox
)
from PySide6.QtCore import Qt

from posture_ai.core.config import save_config

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

        # Fields
        self.spin_camera = QSpinBox()
        self.spin_camera.setRange(0, 10)
        self.spin_camera.setValue(self.config.camera_index)
        self.spin_camera.setStyleSheet("background-color: #1a0533; color: white; padding: 5px; border-radius: 4px;")

        self.spin_fps = QSpinBox()
        self.spin_fps.setRange(1, 60)
        self.spin_fps.setValue(self.config.fps)
        self.spin_fps.setStyleSheet("background-color: #1a0533; color: white; padding: 5px; border-radius: 4px;")

        self.spin_window = QSpinBox()
        self.spin_window.setRange(10, 300)
        self.spin_window.setValue(self.config.temporal_window_size)
        self.spin_window.setStyleSheet("background-color: #1a0533; color: white; padding: 5px; border-radius: 4px;")

        self.spin_cooldown = QSpinBox()
        self.spin_cooldown.setRange(10, 1000)
        self.spin_cooldown.setValue(self.config.cooldown_seconds)
        self.spin_cooldown.setStyleSheet("background-color: #1a0533; color: white; padding: 5px; border-radius: 4px;")

        self.spin_break = QSpinBox()
        self.spin_break.setRange(10, 10000)
        self.spin_break.setValue(self.config.sit_break_threshold_seconds)
        self.spin_break.setStyleSheet("background-color: #1a0533; color: white; padding: 5px; border-radius: 4px;")

        form_layout.addRow(self.create_label("Kamera Indeksi (0 - Asosiy):"), self.spin_camera)
        form_layout.addRow(self.create_label("Kamera FPS lari:"), self.spin_fps)
        form_layout.addRow(self.create_label("Qotib Qolish Kadrlari (Window Size):"), self.spin_window)
        form_layout.addRow(self.create_label("Takroriy Xabar Vaqti (sekund):"), self.spin_cooldown)
        form_layout.addRow(self.create_label("Tanaffus Eslatmasi (sekund):"), self.spin_break)

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
        self.config.sit_break_threshold_seconds = self.spin_break.value()

        try:
            save_config(self.config)
            QMessageBox.information(self, "Muvaffaqiyatli", "Sozlamalaringiz to'liq saqlandi! Ba'zi o'zgarishlar tizim qayta ishga tushganda faollashadi.")
        except Exception as e:
            QMessageBox.warning(self, "Xato", f"Saqlashda muammo vizaga keldi:\n{str(e)}")

    def reset_to_default(self):
        from posture_ai.core.config import AppConfig
        defaults = AppConfig()
        self.spin_camera.setValue(defaults.camera_index)
        self.spin_fps.setValue(defaults.fps)
        self.spin_window.setValue(defaults.temporal_window_size)
        self.spin_cooldown.setValue(defaults.cooldown_seconds)
        self.spin_break.setValue(defaults.sit_break_threshold_seconds)
