import time

import cv2
import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class CameraPage(QWidget):
    """Jonli kamera va pose landmark overlay sahifasi."""

    def __init__(self, max_preview_fps: int = 15):
        super().__init__()
        self._last_frame_ui_at = 0.0
        self._frame_ui_interval = 1.0 / (max(1, int(max_preview_fps)) * 1.15)
        self.init_ui()

    def init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(18)

        title = QLabel("Kamera Kuzatuvi")
        title.setProperty("class", "TitleText")
        layout.addWidget(title)

        self.lbl_camera = QLabel("Kamera qidirilmoqda...")
        self.lbl_camera.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_camera.setMinimumSize(720, 480)
        self.lbl_camera.setStyleSheet(
            "background-color: #05070e; border: 2px solid #1a0533; border-radius: 12px;"
        )
        layout.addWidget(self.lbl_camera, stretch=1)

        self.lbl_live_issues = QLabel("")
        self.lbl_live_issues.setWordWrap(True)
        self.lbl_live_issues.setMinimumHeight(58)
        self.lbl_live_issues.setStyleSheet(
            "background-color: rgba(0, 245, 212, 0.06); "
            "border: 1px solid rgba(0, 245, 212, 0.15); border-radius: 8px; "
            "padding: 10px; font-size: 14px; color: #d0d0d0;"
        )
        self.lbl_live_issues.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.lbl_live_issues)

    def set_camera_error(self, message: str) -> None:
        self.lbl_camera.setText(message)

    def update_metrics(self, result) -> None:
        fatigue_factor_labels = {
            "posture_trend": "trend",
            "low_movement": "harakat",
            "head_drop": "bosh",
            "posture_instability": "barqarorlik",
            "spine_alignment": "spine",
            "shoulder_elevation": "yelka",
        }
        fatigue_factors = getattr(result, "fatigue_factors", {}) or {}
        top_factors = [
            fatigue_factor_labels.get(name, name)
            for name, value in sorted(fatigue_factors.items(), key=lambda item: item[1], reverse=True)
            if value >= 0.35
        ][:3]
        factor_line = ""
        if top_factors:
            factor_line = (
                "<br><span style='color:#a0aabf;'>Charchoq signallari: "
                + ", ".join(top_factors)
                + "</span>"
            )

        if result.skipped:
            self.lbl_live_issues.setText(
                "<span style='color:#ff9f43;'>Kamera oldida odam aniqlanmadi. "
                "Yuzingiz va yelkalaringiz ko'rinsin.</span>"
            )
            return

        if result.issues:
            issues_html = " &nbsp;|&nbsp; ".join(
                f"<span style='color:#ff4d4f; font-weight:bold;'>{issue}</span>"
                for issue in result.issues[:3]
            )
            advice = getattr(result, "fatigue_advice", None)
            advice_line = f"<br><span style='color:#7b61ff;'>{advice}</span>" if advice else ""
            self.lbl_live_issues.setText(issues_html + advice_line + factor_line)
            return

        self.lbl_live_issues.setText(
            "<span style='color:#00f5d4; font-weight:bold;'>Holatingiz yaxshi! "
            "Nuqtalar real vaqtda aniqlanmoqda.</span>"
            + factor_line
        )

    def update_frame(self, frame) -> None:
        if frame is None:
            return
        now = time.monotonic()
        if (now - self._last_frame_ui_at) < self._frame_ui_interval:
            return
        self._last_frame_ui_at = now
        try:
            rgb_image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            h, w, ch = rgb_image.shape
            rgb_image = np.ascontiguousarray(rgb_image)
            bytes_per_line = ch * w
            q_img = QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
            pixmap = QPixmap.fromImage(q_img)
            self.lbl_camera.setPixmap(
                pixmap.scaled(
                    self.lbl_camera.width(),
                    self.lbl_camera.height(),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
        except Exception:
            pass
