"""PostureAI — Asosiy oyna va System Tray boshqaruvchisi.

Tailscale-style ishlaydi:
  - Dastur ishga tushganda tray icon paydo bo'ladi (orqa fonda ishlaydi)
  - Icon rangi holat bo'yicha o'zgaradi (yashil/qizil/sariq)
  - O'ng tugma → kontekst menyu (holat, statistika, sozlamalar)
  - Chap tugma (yoki menyu) → Dashboard oynasini ochish/yopish
  - Oyna yopilganda dastur to'xtamaydi — tray'da davom etadi
"""

import sys
from loguru import logger
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QSystemTrayIcon, QMenu, QStackedWidget, QFrame,
    QWidgetAction,
)
from PySide6.QtGui import QIcon, QAction, QFont
from PySide6.QtCore import Qt, QTimer

from posture_ai.core.config import AppConfig
from posture_ai.database.storage import Storage
from posture_ai.vision.camera_worker import CameraWorker
from posture_ai.os_utils.notifier import send_notification
from posture_ai.os_utils.dimmer import ScreenDimmer
from posture_ai.os_utils.audio_helper import play_alert_for_issue
from posture_ai.gui.styles import MAIN_STYLESHEET
from posture_ai.gui.pages.dashboard import DashboardPage
from posture_ai.gui.pages.calibration import CalibrationPage
from posture_ai.gui.pages.settings import SettingsPage
from posture_ai.gui.tray_icons import get_tray_icon


class DashboardWindow(QMainWindow):
    """Asosiy ilova oynasi + System Tray boshqaruvchisi."""

    def __init__(self, config: AppConfig, storage: Storage, start_minimized: bool = False):
        super().__init__()
        self.config = config
        self.storage = storage
        self.session_id = storage.start_session()
        self._start_minimized = start_minimized
        self._monitoring_active = True

        self.setWindowTitle("PostureAI - AI HEALTH")
        self.resize(1000, 700)
        self.setStyleSheet(MAIN_STYLESHEET)

        # ── Camera Worker ──
        self.worker = CameraWorker(config)
        self.worker.start()

        # ── UI ──
        self.init_ui()
        self.init_tray()

        # ── Worker → UI signal connections ──
        self.worker.metrics_updated.connect(self.page_dashboard.update_metrics)
        self.worker.frame_processed.connect(self.page_dashboard.update_frame)
        self.worker.alert_triggered.connect(self.handle_alert)
        self.worker.metrics_updated.connect(self.on_metrics_updated)

        # ── Dimmer ──
        self.dimmer = ScreenDimmer()
        self.is_dimmed = False

        # ── Periodic DB log (har 60 sekund) ──
        self.log_timer = QTimer(self)
        self.log_timer.timeout.connect(self.log_statistics)
        self.log_timer.start(config.stats_log_interval_seconds * 1000)

        # ── Tray menyu yangilash (har 5 sekund) ──
        self.tray_refresh_timer = QTimer(self)
        self.tray_refresh_timer.timeout.connect(self.refresh_tray_menu)
        self.tray_refresh_timer.start(5000)

        # ── Holat ──
        self.last_result = None
        self.current_tray_status = "idle"

    # ══════════════════════════════════════════════════════
    # UI Setup
    # ══════════════════════════════════════════════════════

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Sidebar
        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(240)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(0, 40, 0, 0)

        logo_label = QLabel("PostureAI")
        logo_label.setStyleSheet(
            "color: #00f5d4; font-size: 28px; font-weight: bold; "
            "margin-left: 20px; margin-bottom: 30px;"
        )
        sidebar_layout.addWidget(logo_label)

        self.btn_dash = QPushButton("  Asosiy Dashboard")
        self.btn_dash.setCheckable(True)
        self.btn_dash.setChecked(True)

        self.btn_calib = QPushButton("  Kalibrovka")
        self.btn_calib.setCheckable(True)

        self.btn_set = QPushButton("  Sozlamalar")
        self.btn_set.setCheckable(True)

        self.btn_dash.clicked.connect(lambda: self.switch_page(0))
        self.btn_calib.clicked.connect(lambda: self.switch_page(1))
        self.btn_set.clicked.connect(lambda: self.switch_page(2))

        sidebar_layout.addWidget(self.btn_dash)
        sidebar_layout.addWidget(self.btn_calib)
        sidebar_layout.addWidget(self.btn_set)
        sidebar_layout.addStretch()

        lbl_version = QLabel("v2.0 — AI HEALTH 2026")
        lbl_version.setStyleSheet("color: #7b61ff; padding: 20px; font-size: 12px;")
        sidebar_layout.addWidget(lbl_version)

        # Stacked pages
        self.stacked_widget = QStackedWidget()

        self.page_dashboard = DashboardPage(self.storage)
        self.page_calib = CalibrationPage(self.config, self.worker)
        self.page_set = SettingsPage(self.config)

        self.stacked_widget.addWidget(self.page_dashboard)
        self.stacked_widget.addWidget(self.page_calib)
        self.stacked_widget.addWidget(self.page_set)

        main_layout.addWidget(sidebar)
        main_layout.addWidget(self.stacked_widget)

    def switch_page(self, index):
        self.btn_dash.setChecked(index == 0)
        self.btn_calib.setChecked(index == 1)
        self.btn_set.setChecked(index == 2)
        self.stacked_widget.setCurrentIndex(index)
        if index == 0:
            self.page_dashboard.update_forecast()

    # ══════════════════════════════════════════════════════
    # System Tray (Tailscale-style)
    # ══════════════════════════════════════════════════════

    def init_tray(self):
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(get_tray_icon("idle"))
        self.tray_icon.setToolTip("PostureAI — Ishga tushmoqda...")

        # Chap tugma → oyna toggle
        self.tray_icon.activated.connect(self.on_tray_activated)

        # Kontekst menyu yaratish
        self.tray_menu = QMenu()
        self._build_tray_menu()
        self.tray_icon.setContextMenu(self.tray_menu)

        self.tray_icon.show()

    def _build_tray_menu(self):
        """Tailscale-style kontekst menyu."""
        menu = self.tray_menu
        menu.clear()
        menu.setStyleSheet(
            "QMenu { background-color: #1a1a2e; color: #ffffff; border: 1px solid #333; "
            "border-radius: 8px; padding: 4px; }"
            "QMenu::item { padding: 6px 20px; }"
            "QMenu::item:selected { background-color: #16213e; }"
            "QMenu::separator { height: 1px; background: #333; margin: 4px 8px; }"
        )

        # ── Holat sarlavhasi ──
        status_text = self._get_status_text()
        status_action = QAction(status_text, self)
        status_action.setEnabled(False)
        font = QFont()
        font.setBold(True)
        status_action.setFont(font)
        menu.addAction(status_action)

        menu.addSeparator()

        # ── Live statistika ──
        if self.last_result and self.last_result.posture_score is not None:
            score_action = QAction(
                f"Ergonomic Score:  {self.last_result.ergonomic_score or '--'}/100", self
            )
            score_action.setEnabled(False)
            menu.addAction(score_action)

            posture_action = QAction(
                f"Posture Score:    {self.last_result.posture_score}/100", self
            )
            posture_action.setEnabled(False)
            menu.addAction(posture_action)

            sit_min = self.last_result.sit_seconds / 60.0
            sit_action = QAction(f"O'tirish vaqti:   {sit_min:.0f} daqiqa", self)
            sit_action.setEnabled(False)
            menu.addAction(sit_action)

        # ── Bugungi statistika ──
        stats = self.storage.get_today_stats()
        if stats["total_samples"] > 0:
            menu.addSeparator()
            today_action = QAction(
                f"Bugun:  {stats['good_pct']}% to'g'ri  |  {stats['alerts_count']} alert",
                self,
            )
            today_action.setEnabled(False)
            menu.addAction(today_action)

        menu.addSeparator()

        # ── Harakatlar ──
        dashboard_action = QAction("Dashboard ochish", self)
        dashboard_action.triggered.connect(self.toggle_dashboard)
        menu.addAction(dashboard_action)

        # Monitoring toggle
        if self._monitoring_active:
            monitor_action = QAction("Monitoringni to'xtatish", self)
            monitor_action.triggered.connect(self.pause_monitoring)
        else:
            monitor_action = QAction("Monitoringni yoqish", self)
            monitor_action.triggered.connect(self.resume_monitoring)
        menu.addAction(monitor_action)

        menu.addSeparator()

        # ── Chiqish ──
        quit_action = QAction("Chiqish", self)
        quit_action.triggered.connect(self.close_app)
        menu.addAction(quit_action)

    def _get_status_text(self) -> str:
        if not self._monitoring_active:
            return "PostureAI — To'xtatilgan"
        if self.last_result is None:
            return "PostureAI — Ishga tushmoqda..."
        if self.last_result.skipped:
            return "PostureAI — Kamera kutilmoqda"
        if self.last_result.status == "good":
            return "PostureAI — Yaxshi holat"
        return "PostureAI — Noto'g'ri holat!"

    def refresh_tray_menu(self):
        """Tray menyusini yangi ma'lumotlar bilan qayta qurish."""
        self._build_tray_menu()
        self.tray_icon.setToolTip(self._get_status_text())

    def on_tray_activated(self, reason):
        """Tray icon bosilganda — dashboard toggle."""
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.toggle_dashboard()
        elif reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.toggle_dashboard()

    def toggle_dashboard(self):
        """Dashboard oynasini ochish yoki yopish."""
        if self.isVisible():
            self.hide()
        else:
            self.showNormal()
            self.activateWindow()
            self.raise_()
            self.switch_page(0)

    # ══════════════════════════════════════════════════════
    # Monitoring Control
    # ══════════════════════════════════════════════════════

    def pause_monitoring(self):
        """Kamera va monitoringni to'xtatish."""
        self._monitoring_active = False
        self.worker.stop()
        self.tray_icon.setIcon(get_tray_icon("off"))
        self.tray_icon.setToolTip("PostureAI — To'xtatilgan")
        logger.info("Monitoring to'xtatildi (foydalanuvchi so'rovi).")

    def resume_monitoring(self):
        """Monitoringni qayta yoqish."""
        self._monitoring_active = True
        self.worker = CameraWorker(self.config)
        self.worker.metrics_updated.connect(self.page_dashboard.update_metrics)
        self.worker.frame_processed.connect(self.page_dashboard.update_frame)
        self.worker.alert_triggered.connect(self.handle_alert)
        self.worker.metrics_updated.connect(self.on_metrics_updated)
        self.worker.start()
        self.tray_icon.setIcon(get_tray_icon("idle"))
        logger.info("Monitoring qayta yoqildi.")

    # ══════════════════════════════════════════════════════
    # Real-time Updates
    # ══════════════════════════════════════════════════════

    def on_metrics_updated(self, result):
        """CameraWorker har kadr natijasini yuboradi."""
        self.last_result = result

        # Dimmer boshqaruvi
        if result.status == "good" and self.is_dimmed:
            self.dimmer.restore()
            self.is_dimmed = False

        # Tray icon rangini yangilash
        if result.skipped:
            new_status = "idle"
        elif result.status == "good":
            new_status = "good"
        else:
            new_status = "bad"

        if new_status != self.current_tray_status:
            self.current_tray_status = new_status
            self.tray_icon.setIcon(get_tray_icon(new_status))

    def handle_alert(self, result):
        """Ogohlantirish kelganda."""
        logger.warning(f"Alert: {result.issues}")
        message = ", ".join(result.issues)

        # Tray notification
        self.tray_icon.showMessage(
            "PostureAI — Diqqat!",
            message,
            QSystemTrayIcon.MessageIcon.Warning,
            4000,
        )

        # Ovozli ogohlantirish
        if result.issues:
            play_alert_for_issue(result.issues[0])

        # Ekran xiraytirish
        if not self.is_dimmed:
            self.dimmer.dim()
            self.is_dimmed = True

        # Alert'ni bazaga yozish
        self.storage.log_alert(result.issues, timestamp=result.timestamp)

    def log_statistics(self):
        if self.last_result and self.last_result.posture_score is not None:
            self.storage.log_posture(self.session_id, self.last_result)

    # ══════════════════════════════════════════════════════
    # Window Events
    # ══════════════════════════════════════════════════════

    def showEvent(self, event):
        """Oyna ochilganda forecast yangilash."""
        super().showEvent(event)
        self.page_dashboard.update_forecast()

    def closeEvent(self, event):
        """Oyna yopilganda — tray'ga yashirish (to'xtamaslik)."""
        event.ignore()
        self.hide()
        if not self._start_minimized:
            # Faqat birinchi marta ko'rsatish
            self.tray_icon.showMessage(
                "PostureAI",
                "Orqa fonda ishlamoqda. Tray ikonkasini bosib qayta oching.",
                QSystemTrayIcon.MessageIcon.Information,
                2000,
            )
            self._start_minimized = True  # Qayta ko'rsatmaslik uchun

    def close_app(self):
        """Dasturni to'liq yopish."""
        logger.info("Dastur yopilmoqda...")
        self.log_timer.stop()
        self.tray_refresh_timer.stop()
        if self._monitoring_active:
            self.worker.stop()
        self.storage.end_session(self.session_id)
        if self.is_dimmed:
            self.dimmer.restore()
        self.tray_icon.hide()
        QApplication.quit()
