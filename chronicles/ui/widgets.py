"""Custom painted widgets for Chronicles Raid Timer."""

from __future__ import annotations

import math
from typing import Optional

from PyQt6.QtCore import QRectF, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QKeySequence, QPainter, QPen
from PyQt6.QtWidgets import QPushButton, QWidget

from chronicles.ui.svg_icons import render_svg_icon, render_svg_pixmap


class ProgressRing(QWidget):
    """Custom-painted radial progress ring with centered SVG emblem and pulse effect."""

    def __init__(
        self,
        icon_key: str = "sword",
        accent_color: str = "#38BDF8",
        size: int = 40,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self._icon_key = icon_key
        self._accent = QColor(accent_color)
        self._track = QColor(255, 255, 255, 28)
        self._progress = 0.0
        self._pulsing = False
        self._pulse_phase = 0.0
        self._show_ring = True
        self.setFixedSize(size, size)

        self._pulse_timer = QTimer(self)
        self._pulse_timer.setInterval(50)
        self._pulse_timer.timeout.connect(self._tick_pulse)

    def set_ring_size(self, size: int) -> None:
        self.setFixedSize(size, size)
        self.update()

    def set_state(
        self,
        icon_key: str,
        accent_color: str,
        progress: float,
        pulsing: bool = False,
        show_ring: bool = True,
    ) -> None:
        self._icon_key = icon_key
        self._accent = QColor(accent_color)
        self._progress = max(0.0, min(1.0, float(progress)))
        self._show_ring = show_ring

        if pulsing != self._pulsing:
            self._pulsing = pulsing
            if pulsing:
                self._pulse_timer.start()
            else:
                self._pulse_timer.stop()
                self._pulse_phase = 0.0
        self.update()

    def _tick_pulse(self) -> None:
        self._pulse_phase = (self._pulse_phase + 0.16) % (2.0 * math.pi)
        self.update()

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        w, h = self.width(), self.height()
        margin = 4.0
        rect = QRectF(margin, margin, w - margin * 2.0, h - margin * 2.0)

        # Subtle glowing backdrop when active or imminent
        if self._pulsing:
            glow_alpha = int(28 + 26 * (0.5 + 0.5 * math.sin(self._pulse_phase)))
            glow_color = QColor(self._accent)
            glow_color.setAlpha(glow_alpha)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(glow_color)
            painter.drawEllipse(rect.adjusted(-2.5, -2.5, 2.5, 2.5))
        else:
            bg = QColor(self._accent)
            bg.setAlpha(20)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(bg)
            painter.drawEllipse(rect)

        if self._show_ring:
            stroke = max(2.2, w * 0.075)
            track_pen = QPen(self._track, stroke, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
            painter.setPen(track_pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(rect)

            if self._progress > 0.005:
                arc_pen = QPen(self._accent, stroke, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
                painter.setPen(arc_pen)
                start_angle = 90 * 16
                span_angle = int(-360.0 * self._progress * 16)
                painter.drawArc(rect, start_angle, span_angle)

        icon_sz = max(12, int(w * 0.48))
        pix = render_svg_pixmap(
            self._icon_key,
            size=icon_sz,
            color=self._accent.name(),
            dpr=self.devicePixelRatioF(),
        )
        ix = (w - icon_sz) / 2.0
        iy = (h - icon_sz) / 2.0
        painter.drawPixmap(int(round(ix)), int(round(iy)), icon_sz, icon_sz, pix)
        painter.end()


class SvgIconButton(QPushButton):
    """Crisp glassmorphic icon button backed by scalable SVG art."""

    def __init__(
        self,
        icon_key: str,
        tooltip: str = "",
        size: int = 24,
        icon_size: int = 14,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self._icon_key = icon_key
        self._icon_size = icon_size
        self._fg = "#CBD5E1"
        self._hover_bg = "rgba(255, 255, 255, 0.14)"
        self._bg = "rgba(255, 255, 255, 0.06)"
        self._border = "rgba(255, 255, 255, 0.10)"
        self.setFixedSize(size, size)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        if tooltip:
            self.setToolTip(tooltip)
        self._refresh()

    def configure(
        self,
        icon_key: Optional[str] = None,
        fg: Optional[str] = None,
        bg: Optional[str] = None,
        hover_bg: Optional[str] = None,
        border: Optional[str] = None,
        tooltip: Optional[str] = None,
    ) -> None:
        if icon_key is not None:
            self._icon_key = icon_key
        if fg is not None:
            self._fg = fg
        if bg is not None:
            self._bg = bg
        if hover_bg is not None:
            self._hover_bg = hover_bg
        if border is not None:
            self._border = border
        if tooltip is not None:
            self.setToolTip(tooltip)
        self._refresh()

    def _refresh(self) -> None:
        self.setIcon(render_svg_icon(self._icon_key, size=self._icon_size, color=self._fg))
        self.setIconSize(self.size() * 0.62)
        self.setStyleSheet(
            f"""
            QPushButton {{
                background: {self._bg};
                border: 1px solid {self._border};
                border-radius: 6px;
                padding: 0px;
            }}
            QPushButton:hover {{
                background: {self._hover_bg};
                border: 1px solid {self._fg};
            }}
            """
        )


class ColorSwatchButton(QPushButton):
    """Interactive color swatch pill button."""

    color_changed = pyqtSignal(str)

    def __init__(self, color_hex: str = "#38BDF8", parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._color = color_hex
        self.setFixedSize(46, 24)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setText(color_hex.upper())
        self._apply()

    @property
    def color_hex(self) -> str:
        return self._color

    def set_color(self, color_hex: str) -> None:
        self._color = color_hex
        self._apply()

    def _apply(self) -> None:
        c = QColor(self._color)
        lum = 0.299 * c.red() + 0.587 * c.green() + 0.114 * c.blue()
        text_fg = "#0B0E14" if lum > 155 else "#F8FAFC"
        self.setText("")
        self.setToolTip(self._color.upper())
        self.setStyleSheet(
            f"""
            QPushButton {{
                background-color: {self._color};
                color: {text_fg};
                border: 2px solid rgba(255, 255, 255, 0.28);
                border-radius: 6px;
            }}
            QPushButton:hover {{
                border: 2px solid #FFFFFF;
            }}
            """
        )


class KeyCaptureButton(QPushButton):
    """Interactive hotkey recorder supporting single keys and modifier combos."""

    key_captured = pyqtSignal(str)

    def __init__(self, binding: str = "F8", parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._binding = binding
        self._recording = False
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(28)
        self.clicked.connect(self._begin_capture)
        self._update_visual()

    @property
    def binding(self) -> str:
        return self._binding

    def set_binding(self, binding: str) -> None:
        self._binding = binding
        self._recording = False
        self._update_visual()

    def _begin_capture(self) -> None:
        self._recording = True
        self.setText("Press key combo... (Esc cancel)")
        self.setStyleSheet(
            """
            QPushButton {
                background: #991B1B;
                color: #FFFFFF;
                border: 1px solid #F87171;
                border-radius: 6px;
                font-weight: bold;
                font-size: 11px;
                padding: 4px 10px;
            }
            """
        )
        self.grabKeyboard()

    def _update_visual(self) -> None:
        label = self._binding if self._binding else "Unbound (Click to set)"
        self.setText(label)
        self.setStyleSheet(
            """
            QPushButton {
                background: #172030;
                color: #38BDF8;
                border: 1px solid #2A3D59;
                border-radius: 6px;
                font-weight: bold;
                font-size: 11px;
                padding: 4px 10px;
            }
            QPushButton:hover {
                background: #1F2E44;
                border: 1px solid #38BDF8;
            }
            """
        )

    def keyPressEvent(self, event) -> None:
        if not self._recording:
            super().keyPressEvent(event)
            return

        key = event.key()
        if key == Qt.Key.Key_Escape:
            self.cancel()
            return

        if key in (Qt.Key.Key_Control, Qt.Key.Key_Shift, Qt.Key.Key_Alt, Qt.Key.Key_Meta):
            return

        parts: list[str] = []
        mods = event.modifiers()
        if mods & Qt.KeyboardModifier.ControlModifier:
            parts.append("Ctrl")
        if mods & Qt.KeyboardModifier.AltModifier:
            parts.append("Alt")
        if mods & Qt.KeyboardModifier.ShiftModifier:
            parts.append("Shift")

        key_text = QKeySequence(key).toString().strip()
        alias_map = {
            "Ins": "Insert",
            "Del": "Delete",
            "PgUp": "Page Up",
            "PgDown": "Page Down",
            "Return": "Enter",
            "ScrollLock": "Scroll Lock",
            "NumLock": "Num Lock",
            "Print": "Print Screen",
        }
        key_text = alias_map.get(key_text, key_text)
        if not key_text:
            key_text = event.text().strip().upper()

        if key_text:
            parts.append(key_text)
            combo = "+".join(parts)
            self._binding = combo
            self.key_captured.emit(combo)

        self._recording = False
        self.releaseKeyboard()
        self._update_visual()

    def cancel(self) -> None:
        if self._recording:
            self._recording = False
            self.releaseKeyboard()
            self._update_visual()
