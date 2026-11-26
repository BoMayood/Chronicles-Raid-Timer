"""Non-intrusive animated on-screen raid toast notification banner."""

from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import QEasingCurve, QPoint, QPropertyAnimation, Qt, QTimer
from PyQt6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen
from PyQt6.QtWidgets import QApplication, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from chronicles.themes import ThemeSpec, THEMES
from chronicles.ui.svg_icons import render_svg_pixmap


class RaidToastBanner(QWidget):
    """Focus-safe animated notification banner displayed in a screen corner."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._theme: ThemeSpec = THEMES["Obsidian Gold"]
        self._accent = QColor("#F5C451")
        self._progress = 1.0
        self._duration_ms = 5500
        self._elapsed_ms = 0

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setFixedSize(330, 74)

        root = QHBoxLayout(self)
        root.setContentsMargins(14, 10, 14, 12)
        root.setSpacing(10)

        self.icon_lbl = QLabel()
        self.icon_lbl.setFixedSize(32, 32)
        self.icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(self.icon_lbl)

        text_col = QVBoxLayout()
        text_col.setContentsMargins(0, 0, 0, 0)
        text_col.setSpacing(2)

        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(6)

        self.title_lbl = QLabel("Crimson Rift")
        self.title_lbl.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        top_row.addWidget(self.title_lbl)

        self.badge_lbl = QLabel("ALERT")
        self.badge_lbl.setFont(QFont("Segoe UI", 7, QFont.Weight.Bold))
        self.badge_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        top_row.addWidget(self.badge_lbl)
        top_row.addStretch(1)
        text_col.addLayout(top_row)

        self.body_lbl = QLabel("Normal phase begins in 5 minutes")
        self.body_lbl.setFont(QFont("Segoe UI", 9))
        text_col.addWidget(self.body_lbl)

        root.addLayout(text_col, 1)

        self._tick_timer = QTimer(self)
        self._tick_timer.setInterval(50)
        self._tick_timer.timeout.connect(self._on_tick)

        self._slide_anim = QPropertyAnimation(self, b"pos", self)
        self._slide_anim.setDuration(240)
        self._slide_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

    def show_alert(
        self,
        title: str,
        badge: str,
        message: str,
        icon_key: str,
        accent_hex: str,
        theme: ThemeSpec,
        corner: str = "bottom_right",
        duration_ms: int = 5500,
    ) -> None:
        self._theme = theme
        self._accent = QColor(accent_hex)
        self._duration_ms = max(2000, duration_ms)
        self._elapsed_ms = 0
        self._progress = 1.0

        self.icon_lbl.setPixmap(render_svg_pixmap(icon_key, size=26, color=accent_hex))
        self.title_lbl.setText(title)
        self.title_lbl.setStyleSheet(f"color: {theme.text_primary}; background: transparent;")
        self.badge_lbl.setText(badge.upper())
        self.badge_lbl.setStyleSheet(
            f"background: rgba(255,255,255,0.10); color: {accent_hex}; "
            f"border: 1px solid {accent_hex}; border-radius: 4px; padding: 1px 6px;"
        )
        self.body_lbl.setText(message)
        self.body_lbl.setStyleSheet(f"color: {theme.text_secondary}; background: transparent;")

        end_pos, start_pos = self._compute_positions(corner)
        self.move(start_pos)
        self.show()
        self.raise_()
        self._slide_anim.stop()
        self._slide_anim.setStartValue(start_pos)
        self._slide_anim.setEndValue(end_pos)
        self._slide_anim.start()
        self._tick_timer.start()
        self.update()

    def _compute_positions(self, corner: str) -> tuple[QPoint, QPoint]:
        screen = QApplication.primaryScreen()
        avail = screen.availableGeometry() if screen else QApplication.screens()[0].availableGeometry()
        pad = 18
        w, h = self.width(), self.height()

        if corner == "top_left":
            end = QPoint(avail.left() + pad, avail.top() + pad)
            start = QPoint(end.x() - 36, end.y())
        elif corner == "top_right":
            end = QPoint(avail.right() - w - pad, avail.top() + pad)
            start = QPoint(end.x() + 36, end.y())
        elif corner == "bottom_left":
            end = QPoint(avail.left() + pad, avail.bottom() - h - pad)
            start = QPoint(end.x() - 36, end.y())
        else:  # bottom_right
            end = QPoint(avail.right() - w - pad, avail.bottom() - h - pad)
            start = QPoint(end.x() + 36, end.y())
        return end, start

    def _on_tick(self) -> None:
        self._elapsed_ms += 50
        self._progress = max(0.0, 1.0 - (self._elapsed_ms / self._duration_ms))
        self.update()
        if self._elapsed_ms >= self._duration_ms:
            self._tick_timer.stop()
            self.hide()

    def mousePressEvent(self, _event) -> None:
        self._tick_timer.stop()
        self.hide()

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        w, h = float(self.width()), float(self.height())

        path = QPainterPath()
        path.addRoundedRect(0.5, 0.5, w - 1.0, h - 1.0, 12.0, 12.0)

        top_c = QColor(self._theme.bg_elevated)
        top_c.setAlpha(242)
        bot_c = QColor(self._theme.bg_primary)
        bot_c.setAlpha(245)

        grad = QLinearGradient(0, 0, 0, h)
        grad.setColorAt(0.0, top_c)
        grad.setColorAt(1.0, bot_c)
        painter.fillPath(path, grad)

        painter.save()
        painter.setClipPath(path)
        painter.fillRect(0, 0, 4, int(h), self._accent)
        painter.fillRect(0, int(h) - 3, int(w * self._progress), 3, self._accent)
        painter.restore()

        border_c = QColor(self._accent)
        border_c.setAlpha(180)
        painter.setPen(QPen(border_c, 1.2))
        painter.drawPath(path)
        painter.end()
