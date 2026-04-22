"""PostureAI — Asosiy oyna va System Tray boshqaruvchisi.

Tailscale-style ishlaydi:
  - Dastur ishga tushganda tray icon paydo bo'ladi (orqa fonda ishlaydi)
  - Icon rangi holat bo'yicha o'zgaradi (yashil/qizil/sariq)
  - O'ng tugma → kontekst menyu (holat, statistika, sozlamalar)
  - Chap tugma (yoki menyu) → Dashboard oynasini ochish/yopish
  - Oyna yopilganda dastur to'xtamaydi — tray'da davom etadi
"""

import sys
from posture_ai.core.logger import logger
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QSystemTrayIcon, QMenu, QStackedWidget, QFrame,
    QWidgetAction,
)
from PySide6.QtGui import QIcon, QAction, QFont
from PySide6.QtCore import Qt, QTimer, QPropertyAnimation, QParallelAnimationGroup, QEasingCurve

from posture_ai.core.config import AppConfig
from posture_ai.database.storage import Storage
from posture_ai.vision.camera_worker import CameraWorker
from posture_ai.os_utils.notifier import send_notification
from posture_ai.os_utils.dimmer import ScreenDimmer
from posture_ai.os_utils.audio_helper import play_alert_for_issue
from posture_ai.gui.styles import MAIN_STYLESHEET
from posture_ai.gui.pages.camera import CameraPage
from posture_ai.gui.pages.dashboard import DashboardPage
from posture_ai.gui.pages.calibration import CalibrationPage
from posture_ai.gui.pages.settings import SettingsPage
from posture_ai.gui.tray_icons import get_tray_icon


class DashboardWindow(QMainWindow):
    """Asosiy ilova oynasi + System Tray boshqaruvchisi."""

    SIDEBAR_EXPANDED_WIDTH = 240
    SIDEBAR_COLLAPSED_WIDTH = 76

    def __init__(self, config: AppConfig, storage: Storage, start_minimized: bool = False):
        super().__init__()
        self.config = config
        self.storage = storage
        self.session_id = storage.start_session()
        self._start_minimized = start_minimized
        self._monitoring_active = True
        self._is_quitting = False
        self._cleanup_done = False
        self._sidebar_collapsed = False
        self._sidebar_animation: QParallelAnimationGroup | None = None

        self.setWindowTitle("PostureAI - AI HEALTH")
        self.resize(1000, 700)
        self.setStyleSheet(MAIN_STYLESHEET)

        # ── Holat (boshqa modullar ishlatishidan oldin) ──
        self.last_result = None
        self.current_tray_status = "idle"
        self.dimmer = ScreenDimmer()

        # ── Camera Worker ──
        self.worker = CameraWorker(config)

        # ── UI ──
        self.init_ui()
        self.init_tray()

        # ── Worker → UI signal connections ──
        self.worker.metrics_updated.connect(self.page_camera.update_metrics)
        self.worker.metrics_updated.connect(self.page_dashboard.update_metrics)
        self.worker.frame_processed.connect(self.page_camera.update_frame)
        self.worker.alert_triggered.connect(self.handle_alert)
        self.worker.metrics_updated.connect(self.on_metrics_updated)
        self.worker.camera_error.connect(self.on_camera_error)
        self.worker.start()

        # ── Periodic DB log (har 60 sekund) ──
        self.log_timer = QTimer(self)
        self.log_timer.timeout.connect(self.log_statistics)
        self.log_timer.start(config.stats_log_interval_seconds * 1000)

        # ── Tray menyu yangilash (har 5 sekund) ──
        self.tray_refresh_timer = QTimer(self)
        self.tray_refresh_timer.timeout.connect(self.refresh_tray_menu)
        self.tray_refresh_timer.start(5000)

        self._sync_live_preview_mode()

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
        self.sidebar = QFrame()
        self.sidebar.setObjectName("Sidebar")
        self.sidebar.setProperty("collapsed", False)
        self.sidebar.setFixedWidth(self.SIDEBAR_EXPANDED_WIDTH)
        sidebar_layout = QVBoxLayout(self.sidebar)
        sidebar_layout.setContentsMargins(0, 40, 0, 0)

        self.sidebar_header_layout = QHBoxLayout()
        self.sidebar_header_layout.setContentsMargins(20, 0, 14, 24)
        self.sidebar_header_layout.setSpacing(8)

        self.logo_label = QLabel("PostureAI")
        self.logo_label.setObjectName("SidebarLogo")
        self.sidebar_header_layout.addWidget(self.logo_label, stretch=1)

        self.btn_sidebar_toggle = QPushButton("☰")
        self.btn_sidebar_toggle.setObjectName("SidebarToggle")
        self.btn_sidebar_toggle.setFixedSize(42, 42)
        self.btn_sidebar_toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_sidebar_toggle.setToolTip("Sidebarni yopish")
        self.btn_sidebar_toggle.clicked.connect(self.toggle_sidebar)
        self.sidebar_header_layout.addWidget(self.btn_sidebar_toggle)
        sidebar_layout.addLayout(self.sidebar_header_layout)

        self.btn_camera = QPushButton("◉  Kamera")
        self.btn_camera.setObjectName("NavButton")
        self.btn_camera.setCheckable(True)
        self.btn_camera.setChecked(True)

        self.btn_dash = QPushButton("▦  Analiz")
        self.btn_dash.setObjectName("NavButton")
        self.btn_dash.setCheckable(True)

        self.btn_calib = QPushButton("◎  Kalibrovka")
        self.btn_calib.setObjectName("NavButton")
        self.btn_calib.setCheckable(True)

        self.btn_set = QPushButton("⚙  Sozlamalar")
        self.btn_set.setObjectName("NavButton")
        self.btn_set.setCheckable(True)

        self._nav_buttons = [
            (self.btn_camera, "◉  Kamera", "◉", "Kamera"),
            (self.btn_dash, "▦  Analiz", "▦", "Analiz"),
            (self.btn_calib, "◎  Kalibrovka", "◎", "Kalibrovka"),
            (self.btn_set, "⚙  Sozlamalar", "⚙", "Sozlamalar"),
        ]
        for button, _expanded_text, _collapsed_text, tooltip in self._nav_buttons:
            button.setMinimumHeight(52)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setToolTip(tooltip)

        self.btn_camera.clicked.connect(lambda: self.switch_page(0))
        self.btn_dash.clicked.connect(lambda: self.switch_page(1))
        self.btn_calib.clicked.connect(lambda: self.switch_page(2))
        self.btn_set.clicked.connect(lambda: self.switch_page(3))

        sidebar_layout.addWidget(self.btn_camera)
        sidebar_layout.addWidget(self.btn_dash)
        sidebar_layout.addWidget(self.btn_calib)
        sidebar_layout.addWidget(self.btn_set)
        sidebar_layout.addStretch()

        self.lbl_version = QLabel("v2.0 — AI HEALTH 2026")
        self.lbl_version.setObjectName("SidebarVersion")
        self.lbl_version.setAlignment(Qt.AlignmentFlag.AlignLeft)
        sidebar_layout.addWidget(self.lbl_version)

        # Stacked pages
        self.stacked_widget = QStackedWidget()

        self.page_camera = CameraPage(max_preview_fps=getattr(self.config, "preview_fps", 15))
        self.page_dashboard = DashboardPage(self.storage)
        self.page_calib = CalibrationPage(self.config, self.worker)
        self.page_set = SettingsPage(self.config)

        self.stacked_widget.addWidget(self.page_camera)
        self.stacked_widget.addWidget(self.page_dashboard)
        self.stacked_widget.addWidget(self.page_calib)
        self.stacked_widget.addWidget(self.page_set)

        main_layout.addWidget(self.sidebar)
        main_layout.addWidget(self.stacked_widget)

    def toggle_sidebar(self):
        self.set_sidebar_collapsed(not self._sidebar_collapsed)

    def set_sidebar_collapsed(self, collapsed: bool) -> None:
        self._sidebar_collapsed = collapsed
        target_width = self.SIDEBAR_COLLAPSED_WIDTH if collapsed else self.SIDEBAR_EXPANDED_WIDTH
        current_width = self.sidebar.width()

        self.sidebar.setProperty("collapsed", collapsed)
        self.sidebar.style().unpolish(self.sidebar)
        self.sidebar.style().polish(self.sidebar)

        self.logo_label.setVisible(not collapsed)
        self.logo_label.setText("PostureAI")
        if collapsed:
            self.sidebar_header_layout.setContentsMargins(17, 0, 17, 24)
            self.sidebar_header_layout.setSpacing(0)
        else:
            self.sidebar_header_layout.setContentsMargins(20, 0, 14, 24)
            self.sidebar_header_layout.setSpacing(8)
        self.lbl_version.setText("v2.0" if collapsed else "v2.0 — AI HEALTH 2026")
        self.lbl_version.setAlignment(Qt.AlignmentFlag.AlignCenter if collapsed else Qt.AlignmentFlag.AlignLeft)
        self.btn_sidebar_toggle.setText("»" if collapsed else "☰")
        self.btn_sidebar_toggle.setToolTip("Sidebarni ochish" if collapsed else "Sidebarni yopish")

        for button, expanded_text, collapsed_text, _tooltip in self._nav_buttons:
            button.setText(collapsed_text if collapsed else expanded_text)

        if self._sidebar_animation is not None and self._sidebar_animation.state():
            self._sidebar_animation.stop()

        group = QParallelAnimationGroup(self)
        for prop_name in (b"minimumWidth", b"maximumWidth"):
            animation = QPropertyAnimation(self.sidebar, prop_name, group)
            animation.setDuration(180)
            animation.setStartValue(current_width)
            animation.setEndValue(target_width)
            animation.setEasingCurve(QEasingCurve.Type.InOutCubic)
            group.addAnimation(animation)
        group.finished.connect(lambda: self.sidebar.setFixedWidth(target_width))
        self._sidebar_animation = group
        group.start()

    def switch_page(self, index):
        self.btn_camera.setChecked(index == 0)
        self.btn_dash.setChecked(index == 1)
        self.btn_calib.setChecked(index == 2)
        self.btn_set.setChecked(index == 3)
        self.stacked_widget.setCurrentIndex(index)
        self._sync_live_preview_mode()
        if index == 1:
            self.page_dashboard.update_forecast()

    def _sync_live_preview_mode(self) -> None:
        if getattr(self, "worker", None) is None:
            return
        is_camera_page_visible = self.isVisible() and self.stacked_widget.currentIndex() == 0
        self.worker.set_live_preview_mode(is_camera_page_visible)

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
        dashboard_action = QAction("Ilovani ochish", self)
        dashboard_action.triggered.connect(self.toggle_dashboard)
        menu.addAction(dashboard_action)

        camera_action = QAction("Kamera sahifasi", self)
        camera_action.triggered.connect(lambda _checked=False: self.open_page_from_tray(0))
        menu.addAction(camera_action)

        analysis_action = QAction("Analiz sahifasi", self)
        analysis_action.triggered.connect(lambda _checked=False: self.open_page_from_tray(1))
        menu.addAction(analysis_action)

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
            self._sync_live_preview_mode()
        else:
            self.showNormal()
            self.activateWindow()
            self.raise_()
            self.switch_page(0)

    def open_page_from_tray(self, index: int):
        self.showNormal()
        self.activateWindow()
        self.raise_()
        self.switch_page(index)

    # ══════════════════════════════════════════════════════
    # Monitoring Control
    # ══════════════════════════════════════════════════════

    def pause_monitoring(self):
        """Kamera va monitoringni to'xtatish."""
        self._monitoring_active = False
        self._stop_worker()
        self.tray_icon.setIcon(get_tray_icon("off"))
        self.tray_icon.setToolTip("PostureAI — To'xtatilgan")
        logger.info("Monitoring to'xtatildi (foydalanuvchi so'rovi).")

    def resume_monitoring(self):
        """Monitoringni qayta yoqish."""
        # Eski worker hali ishlayotgan bo'lsa — to'xtatish
        self._stop_worker()

        self._monitoring_active = True
        self.worker = CameraWorker(self.config)
        self.worker.metrics_updated.connect(self.page_camera.update_metrics)
        self.worker.metrics_updated.connect(self.page_dashboard.update_metrics)
        self.worker.frame_processed.connect(self.page_camera.update_frame)
        self.worker.alert_triggered.connect(self.handle_alert)
        self.worker.metrics_updated.connect(self.on_metrics_updated)
        self.worker.camera_error.connect(self.on_camera_error)
        self._sync_live_preview_mode()
        self.worker.start()
        # Kalibrovka sahifasiga yangi worker'ni berish
        self.page_calib.worker = self.worker
        self.tray_icon.setIcon(get_tray_icon("idle"))
        logger.info("Monitoring qayta yoqildi.")

    # ══════════════════════════════════════════════════════
    # Real-time Updates
    # ══════════════════════════════════════════════════════

    def on_camera_error(self, error_msg: str):
        """Kamera xatosi — foydalanuvchiga xabar berish."""
        logger.error(f"Kamera xatosi: {error_msg}")
        self._monitoring_active = False
        self.tray_icon.setIcon(get_tray_icon("off"))
        self.tray_icon.setToolTip("PostureAI — Kamera topilmadi")
        self.tray_icon.showMessage(
            "PostureAI — Kamera xatosi",
            "Kamerani ulang va monitoringni qayta yoqing.",
            QSystemTrayIcon.MessageIcon.Critical,
            5000,
        )
        self.page_camera.set_camera_error(
            "Kamera topilmadi.\nSozlamalardan kamera indeksini tekshiring\n"
            "yoki kamerani ulang va monitoringni qayta yoqing."
        )

    def on_metrics_updated(self, result):
        """CameraWorker har kadr natijasini yuboradi."""
        self.last_result = result

        # Dimmer boshqaruvi
        if result.status == "good" and self.dimmer.is_dimmed:
            self.dimmer.restore()

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
        message = (
            result.fatigue_advice
            if getattr(result, "fatigue_alert", False) and getattr(result, "fatigue_advice", None)
            else ", ".join(result.issues)
        )

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
        if not self.dimmer.is_dimmed:
            self.dimmer.dim()

        # Alert'ni bazaga yozish
        self.storage.log_alert(result.issues, timestamp=result.timestamp)

    def log_statistics(self):
        if self.last_result and self.last_result.posture_score is not None:
            self.storage.log_posture(self.session_id, self.last_result)

    # ══════════════════════════════════════════════════════
    # Window Events
    # ══════════════════════════════════════════════════════

    def _stop_worker(self):
        """CameraWorker'ni deterministik to'xtatish."""
        if getattr(self, "worker", None) is None:
            return
        if self.worker.isRunning():
            self.worker.stop()
            if not self.worker.wait(5000):
                logger.warning("Worker thread vaqtida to'xtamadi, terminate qilinmoqda.")
                self.worker.terminate()
                self.worker.wait(2000)

    def _cleanup_before_quit(self):
        """QApplication tugashidan oldin kamera, timer va OS resurslarini yopish."""
        if self._cleanup_done:
            return
        self._cleanup_done = True
        self._is_quitting = True
        logger.info("Dastur yopilmoqda...")

        if getattr(self, "log_timer", None) is not None:
            self.log_timer.stop()
        if getattr(self, "tray_refresh_timer", None) is not None:
            self.tray_refresh_timer.stop()

        self._stop_worker()
        self.storage.end_session(self.session_id)
        if self.dimmer.is_dimmed:
            self.dimmer.restore()
        if getattr(self, "tray_icon", None) is not None:
            self.tray_icon.hide()

    def showEvent(self, event):
        """Oyna ochilganda forecast yangilash."""
        super().showEvent(event)
        self._sync_live_preview_mode()
        self.page_dashboard.update_forecast()

    def closeEvent(self, event):
        """Oyna yopilganda — tray'ga yashirish (to'xtamaslik)."""
        if self._is_quitting:
            event.accept()
            return
        event.ignore()
        self.hide()
        self._sync_live_preview_mode()
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
        self._cleanup_before_quit()
        QApplication.quit()
