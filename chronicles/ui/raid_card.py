"""Next-gen Tactical Raid Card supporting responsive shrinking with zero text overlap."""

from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import QSize, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QFontMetrics, QLinearGradient, QPainter, QPainterPath, QPen, QRadialGradient
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from chronicles.models import RaidStatus
from chronicles.schedule_engine import format_countdown, format_local_time
from chronicles.themes import ThemeSpec, THEMES
from chronicles.ui.svg_icons import render_svg_icon
from chronicles.ui.widgets import ProgressRing


class TacticalRaidCard(QFrame):
    """Custom-painted glassmorphic raid telemetry card with adaptive narrow layout."""

    snooze_requested = pyqtSignal(str)
    manual_reset_requested = pyqtSignal(str)

    def __init__(self, raid_id: str, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.raid_id = raid_id
        self._theme: ThemeSpec = THEMES["Obsidian Gold"]
        self._mode: str = "cards"  # "cards" | "compact" | "horizontal"
        self._font_scale: float = 1.0
        self._show_rings: bool = True
        self._use_24h: bool = False
        self._locked: bool = False
        self._status: Optional[RaidStatus] = None
        self._accent = QColor("#38BDF8")
        self._progress = 0.0
        self._is_active = False
        self._is_imminent = False
        self._hovered = False

        self._full_name = "Raid"
        self._full_schedule = ""
        self._short_schedule = ""

        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.setMouseTracking(True)
        self._build_ui()

    def _build_ui(self) -> None:
        self._root = QVBoxLayout(self)
        self._root.setContentsMargins(9, 6, 9, 7)
        self._root.setSpacing(2)

        self._row = QHBoxLayout()
        self._row.setContentsMargins(0, 0, 0, 0)
        self._row.setSpacing(8)

        self.ring = ProgressRing("sword", "#38BDF8", size=34, parent=self)
        self._row.addWidget(self.ring, 0, Qt.AlignmentFlag.AlignVCenter)

        # Center info stack (stretches/shrinks cleanly)
        self._center_box = QVBoxLayout()
        self._center_box.setContentsMargins(0, 0, 0, 0)
        self._center_box.setSpacing(1)

        self._title_row = QHBoxLayout()
        self._title_row.setContentsMargins(0, 0, 0, 0)
        self._title_row.setSpacing(5)

        self.name_lbl = QLabel("Raid")
        self.name_lbl.setMinimumWidth(20)
        self.name_lbl.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        self._title_row.addWidget(self.name_lbl, 1)

        self.phase_badge = QLabel("NORM")
        self.phase_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.phase_badge.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self._title_row.addWidget(self.phase_badge, 0)

        self._center_box.addLayout(self._title_row)

        self._meta_row = QHBoxLayout()
        self._meta_row.setContentsMargins(0, 0, 0, 0)
        self._meta_row.setSpacing(5)

        self.schedule_lbl = QLabel("")
        self.schedule_lbl.setMinimumWidth(20)
        self.schedule_lbl.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        self._meta_row.addWidget(self.schedule_lbl, 1)

        self.manual_btn = QPushButton("Reset")
        self.manual_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.manual_btn.setFixedHeight(17)
        self.manual_btn.setVisible(False)
        self.manual_btn.clicked.connect(lambda: self.manual_reset_requested.emit(self.raid_id))
        self._meta_row.addWidget(self.manual_btn, 0)

        self._center_box.addLayout(self._meta_row)
        self._row.addLayout(self._center_box, 1)

        # Right countdown stack (never clipped)
        self._right_box = QVBoxLayout()
        self._right_box.setContentsMargins(0, 0, 0, 0)
        self._right_box.setSpacing(0)

        self._prefix_row = QHBoxLayout()
        self._prefix_row.setContentsMargins(0, 0, 0, 0)
        self._prefix_row.setSpacing(3)
        self._prefix_row.addStretch(1)

        self.snooze_btn = QPushButton()
        self.snooze_btn.setFixedSize(15, 15)
        self.snooze_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.snooze_btn.setToolTip("Snooze alert for this raid cycle")
        self.snooze_btn.clicked.connect(lambda: self.snooze_requested.emit(self.raid_id))
        self.snooze_btn.setVisible(False)
        self._prefix_row.addWidget(self.snooze_btn)

        self.prefix_lbl = QLabel("STARTS IN")
        self.prefix_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.prefix_lbl.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self._prefix_row.addWidget(self.prefix_lbl)

        self._right_box.addLayout(self._prefix_row)

        self.countdown_lbl = QLabel("00:00:00")
        self.countdown_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.countdown_lbl.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self._right_box.addWidget(self.countdown_lbl)

        self._row.addLayout(self._right_box, 0)
        self._root.addLayout(self._row)
        self._apply_typography()

    def minimumSizeHint(self) -> QSize:
        s = self._font_scale
        self._root.activate()
        layout_min_h = self._root.minimumSize().height()
        if self._mode == "compact":
            return QSize(max(195, int(205 * s)), max(30, int(34 * s), layout_min_h))
        if self._mode == "horizontal":
            return QSize(max(265, int(295 * s)), max(48, int(54 * s), layout_min_h))
        return QSize(max(200, int(210 * s)), max(48, int(54 * s), layout_min_h))

    def sizeHint(self) -> QSize:
        s = self._font_scale
        if self._mode == "compact":
            return QSize(int(360 * s), int(38 * s))
        if self._mode == "horizontal":
            return QSize(int(305 * s), int(58 * s))
        return QSize(int(385 * s), int(60 * s))

    def set_theme(self, theme: ThemeSpec) -> None:
        self._theme = theme
        self._refresh_visuals()

    def set_options(
        self,
        mode: str,
        font_scale: float,
        show_rings: bool,
        use_24h: bool,
        locked: bool,
    ) -> None:
        self._mode = mode
        self._font_scale = font_scale
        self._show_rings = show_rings
        self._use_24h = use_24h
        self._locked = locked
        self._apply_layout_mode()
        self._apply_typography()
        self._refresh_visuals()

    def _apply_layout_mode(self) -> None:
        s = self._font_scale
        if self._mode == "compact":
            self._root.setContentsMargins(8, 3, 8, 4)
            self._row.setSpacing(6)
            self.ring.set_ring_size(max(18, int(22 * s)))
            self.schedule_lbl.setVisible(False)
            self.prefix_lbl.setVisible(False)
            self.snooze_btn.setVisible(False)
        elif self._mode == "horizontal":
            self._root.setContentsMargins(9, 5, 9, 6)
            self._row.setSpacing(7)
            self.ring.set_ring_size(max(24, int(30 * s)))
            self.schedule_lbl.setVisible(True)
            self.prefix_lbl.setVisible(True)
        else:
            self._root.setContentsMargins(9, 6, 9, 7)
            self._row.setSpacing(8)
            self.ring.set_ring_size(max(26, int(34 * s)))
            self.schedule_lbl.setVisible(True)
            self.prefix_lbl.setVisible(True)
        self.updateGeometry()

    def _apply_typography(self) -> None:
        s = self._font_scale
        narrow = self.width() > 0 and self.width() < 265
        name_pt = max(7, int(round((8.8 if narrow or self._mode == "compact" else 10.0) * s)))
        badge_pt = max(6, int(round((6.8 if narrow else 7.3) * s)))
        meta_pt = max(6, int(round((7.4 if narrow else 8.0) * s)))
        prefix_pt = max(6, int(round(6.8 * s)))
        cd_pt = max(9, int(round((10.5 if self._mode == "compact" or narrow else 13.0) * s)))

        self.name_lbl.setFont(QFont("Segoe UI", name_pt, QFont.Weight.Bold))
        self.phase_badge.setFont(QFont("Segoe UI", badge_pt, QFont.Weight.Bold))
        self.schedule_lbl.setFont(QFont("Segoe UI", meta_pt, QFont.Weight.Medium))
        self.prefix_lbl.setFont(QFont("Segoe UI", prefix_pt, QFont.Weight.Bold))
        self.countdown_lbl.setFont(QFont("Consolas", cd_pt, QFont.Weight.Bold))
        self.manual_btn.setFont(QFont("Segoe UI", max(6, int(7.2 * s)), QFont.Weight.Bold))

    def update_status(self, status: RaidStatus) -> None:
        self._status = status
        self._refresh_visuals()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._apply_typography()
        if self._status is not None:
            self._refresh_visuals()
        else:
            self._fit_responsive_labels()

    def _fit_responsive_labels(self) -> None:
        w = self.width()
        s = self._font_scale
        if w <= 0:
            return

        # Adapt ring size / visibility for ultra-narrow HUD widths
        if w < 228:
            self.ring.setVisible(False)
        else:
            self.ring.setVisible(True)
            if self._mode == "compact":
                self.ring.set_ring_size(max(18, int((19 if w < 280 else 22) * s)))
            else:
                self.ring.set_ring_size(max(22, int((25 if w < 290 else 33) * s)))

        self.phase_badge.adjustSize()
        self._title_row.activate()

        # Elide raid title & schedule text cleanly based on actual available width
        ring_used = (self.ring.width() + self._row.spacing()) if self.ring.isVisible() else 0
        prefix_w = (self.prefix_lbl.sizeHint().width() + (18 if self.snooze_btn.isVisible() else 0)) if self.prefix_lbl.isVisible() else 0
        right_used = max(self.countdown_lbl.sizeHint().width(), prefix_w, 64) + self._row.spacing() + 20
        avail_center = max(48, w - ring_used - right_used)

        badge_w = self.phase_badge.sizeHint().width() + 6
        name_avail = max(36, avail_center - badge_w)
        fm_name = QFontMetrics(self.name_lbl.font())
        self.name_lbl.setText(fm_name.elidedText(self._full_name, Qt.TextElideMode.ElideRight, name_avail))

        if self.schedule_lbl.isVisible():
            manual_w = (self.manual_btn.sizeHint().width() + 6) if self.manual_btn.isVisible() else 0
            sched_avail = max(30, avail_center - manual_w)
            fm_sched = QFontMetrics(self.schedule_lbl.font())
            chosen = self._short_schedule if w < int(330 * s) else self._full_schedule
            self.schedule_lbl.setText(fm_sched.elidedText(chosen, Qt.TextElideMode.ElideRight, sched_avail))

    def _refresh_visuals(self) -> None:
        if self._status is None:
            return
        st = self._status
        raid = st.raid
        t = self._theme
        narrow = self.width() > 0 and self.width() < int(315 * self._font_scale)

        self._accent = QColor(raid.accent_color)
        self._progress = st.progress
        self._is_active = st.is_active
        self._is_imminent = st.is_imminent and not st.is_snoozed
        self._full_name = raid.name
        self.name_lbl.setStyleSheet(f"color: {t.text_primary}; background: transparent; border: none;")

        is_manual = raid.schedule_kind == "interval_manual"
        self.manual_btn.setVisible(is_manual and not self._locked and self._mode != "compact")
        self.manual_btn.setText("Start" if not st.is_configured else "Reset")
        self.manual_btn.setStyleSheet(
            f"""
            QPushButton {{
                background: rgba(255, 255, 255, 0.08);
                color: {raid.accent_color};
                border: 1px solid {raid.accent_color};
                border-radius: 4px;
                padding: 1px 6px;
            }}
            QPushButton:hover {{
                background: {raid.accent_color};
                color: #0B0E14;
            }}
            """
        )

        ring_color = raid.accent_color
        if st.is_active:
            ring_color = t.live_hard_fg if st.is_hard else t.live_normal_fg
        elif st.is_imminent and not st.is_snoozed:
            ring_color = t.warning_fg

        self.ring.set_state(
            icon_key=raid.icon_key,
            accent_color=ring_color,
            progress=st.progress,
            pulsing=(st.is_active or (st.is_imminent and not st.is_snoozed)),
            show_ring=self._show_rings,
        )

        can_snooze = (not self._locked) and self._mode != "compact" and st.is_configured
        self.snooze_btn.setVisible(can_snooze and (self._hovered or st.is_snoozed))
        snooze_color = t.warning_fg if st.is_snoozed else t.text_muted
        self.snooze_btn.setIcon(render_svg_icon("snooze", size=12, color=snooze_color))
        self.snooze_btn.setStyleSheet(
            "QPushButton { background: transparent; border: none; padding: 0px; }"
            "QPushButton:hover { background: rgba(255,255,255,0.12); border-radius: 4px; }"
        )

        pad_badge = "1px 5px" if narrow else "1px 6px"

        if not st.is_configured:
            self.phase_badge.setText("IDLE" if narrow else "STANDBY")
            self.phase_badge.setStyleSheet(
                f"background: {t.bg_elevated}; color: {t.text_muted}; "
                f"border: 1px solid {t.border_subtle}; border-radius: 4px; padding: {pad_badge};"
            )
            self.prefix_lbl.setText("MANUAL")
            self.prefix_lbl.setStyleSheet(f"color: {t.text_muted}; background: transparent;")
            self.countdown_lbl.setText("--:--:--")
            self.countdown_lbl.setStyleSheet(f"color: {t.text_muted}; background: transparent;")
            self._full_schedule = f"Interval: {raid.interval_minutes}m respawn"
            self._short_schedule = f"{raid.interval_minutes}m cycle"
            self.schedule_lbl.setStyleSheet(f"color: {t.text_muted}; background: transparent;")
        elif st.is_active:
            fg = t.live_hard_fg if st.is_hard else t.live_normal_fg
            bg = t.live_hard_bg if st.is_hard else t.live_normal_bg
            self.phase_badge.setText(
                ("HARD" if st.is_hard else "LIVE") if narrow else f"LIVE • {st.phase_label.upper()}"
            )
            self.phase_badge.setStyleSheet(
                f"background: {bg}; color: {fg}; border: 1px solid {fg}; "
                f"border-radius: 4px; padding: {pad_badge};"
            )
            self.prefix_lbl.setText("ENDS IN")
            self.prefix_lbl.setStyleSheet(f"color: {fg}; background: transparent;")
            self.countdown_lbl.setText(format_countdown(st.seconds_left))
            self.countdown_lbl.setStyleSheet(f"color: {fg}; background: transparent;")

            if st.next_window and not st.is_hard and raid.hard_duration_min > 0:
                t_nxt = format_local_time(st.next_window.start_ts, self._use_24h)
                self._full_schedule = f"{raid.hard_label} opens {t_nxt}"
                self._short_schedule = f"{raid.hard_label} {t_nxt}"
            elif st.active_window:
                t_end = format_local_time(st.active_window.end_ts, self._use_24h)
                self._full_schedule = f"Ends at {t_end}"
                self._short_schedule = f"Ends {t_end}"
            self.schedule_lbl.setStyleSheet(f"color: {t.text_secondary}; background: transparent;")
        else:
            fg = t.hard_fg if st.is_hard else t.normal_fg
            bg = t.hard_bg if st.is_hard else t.normal_bg
            if st.is_snoozed:
                badge_text = "SNZ" if narrow else f"{st.phase_label.upper()} • SNZ"
            elif st.is_imminent:
                badge_text = "SOON"
            else:
                badge_text = st.phase_label[:4].upper() if narrow else st.phase_label.upper()
            self.phase_badge.setText(badge_text)
            border_c = t.warning_fg if (st.is_imminent and not st.is_snoozed) else fg
            self.phase_badge.setStyleSheet(
                f"background: {bg}; color: {fg}; border: 1px solid {border_c}; "
                f"border-radius: 4px; padding: {pad_badge};"
            )

            cd_color = t.warning_fg if (st.is_imminent and not st.is_snoozed) else raid.accent_color
            self.prefix_lbl.setText("STARTS IN")
            self.prefix_lbl.setStyleSheet(f"color: {t.text_muted}; background: transparent;")
            self.countdown_lbl.setText(format_countdown(st.seconds_left))
            self.countdown_lbl.setStyleSheet(f"color: {cd_color}; background: transparent;")

            if st.next_window and st.following_window and raid.hard_duration_min > 0 and not st.is_hard:
                t1 = format_local_time(st.next_window.start_ts, self._use_24h)
                t2 = format_local_time(st.following_window.start_ts, self._use_24h)
                self._full_schedule = f"{raid.normal_label} {t1}  •  {raid.hard_label} {t2}"
                self._short_schedule = f"{t1} • {raid.hard_label} {t2}"
            elif st.next_window:
                t1 = format_local_time(st.next_window.start_ts, self._use_24h)
                self._full_schedule = f"Next: {st.next_window.phase_label} at {t1}"
                self._short_schedule = f"{st.next_window.phase_label} {t1}"
            self.schedule_lbl.setStyleSheet(f"color: {t.text_muted}; background: transparent;")

        self._fit_responsive_labels()
        self.update()

    def enterEvent(self, event) -> None:
        self._hovered = True
        self._refresh_visuals()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._hovered = False
        self._refresh_visuals()
        super().leaveEvent(event)

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        w, h = float(self.width()), float(self.height())
        radius = 8.0 if self._mode == "compact" else 10.0
        rect = self.rect().adjusted(1, 1, -1, -1)

        path = QPainterPath()
        path.addRoundedRect(0.5, 0.5, w - 1.0, h - 1.0, radius, radius)

        base_hex = self._theme.card_hover if (self._hovered and not self._locked) else self._theme.card_bg
        base_c = QColor(base_hex)
        base_c.setAlpha(212 if not self._locked else 188)
        bottom_c = QColor(self._theme.bg_primary)
        bottom_c.setAlpha(224 if not self._locked else 196)

        grad = QLinearGradient(0, 0, 0, h)
        grad.setColorAt(0.0, base_c)
        grad.setColorAt(1.0, bottom_c)
        painter.fillPath(path, grad)

        if self._is_active or self._is_imminent:
            bloom_c = QColor(self._accent)
            if self._is_active and self._status is not None:
                bloom_c = QColor(
                    self._theme.live_hard_fg if self._status.is_hard else self._theme.live_normal_fg
                )
            elif self._is_imminent:
                bloom_c = QColor(self._theme.warning_fg)
            bloom = QRadialGradient(18.0, h * 0.5, w * 0.55)
            c0 = QColor(bloom_c)
            c0.setAlpha(46 if self._is_active else 30)
            c1 = QColor(bloom_c)
            c1.setAlpha(0)
            bloom.setColorAt(0.0, c0)
            bloom.setColorAt(1.0, c1)
            painter.save()
            painter.setClipPath(path)
            painter.fillRect(rect, bloom)
            painter.restore()

        bar_color = QColor(self._accent)
        if self._is_active and self._status is not None:
            bar_color = QColor(
                self._theme.live_hard_fg if self._status.is_hard else self._theme.live_normal_fg
            )
        painter.save()
        painter.setClipPath(path)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(bar_color)
        painter.drawRoundedRect(3, 5, 3, max(8, int(h) - 10), 1.5, 1.5)

        if self._progress > 0.005:
            track = QColor(255, 255, 255, 16)
            painter.fillRect(0, int(h) - 3, int(w), 3, track)
            fill_c = QColor(bar_color)
            fill_c.setAlpha(215)
            painter.fillRect(0, int(h) - 3, max(4, int(w * self._progress)), 3, fill_c)
        painter.restore()

        border_c = QColor(self._theme.border_subtle)
        if self._is_active:
            border_c = QColor(bar_color)
            border_c.setAlpha(175)
        elif self._is_imminent:
            border_c = QColor(self._theme.warning_fg)
            border_c.setAlpha(155)
        painter.setPen(QPen(border_c, 1.0))
        painter.drawPath(path)
        painter.end()
