"""Interactive 24-hour custom-painted local & UTC raid timeline widget."""

from __future__ import annotations

import time
from datetime import datetime
from typing import Optional

from PyQt6.QtCore import QRectF, Qt
from PyQt6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PyQt6.QtWidgets import QToolTip, QWidget

from chronicles.models import RaidDefinition, RaidWindow
from chronicles.schedule_engine import build_timeline_windows, format_local_time, format_utc_time
from chronicles.themes import ThemeSpec, THEMES


class RaidTimelineWidget(QWidget):
    """Visual 24-hour raid schedule swimlane timeline with hover inspection."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._raids: list[RaidDefinition] = []
        self._windows: list[RaidWindow] = []
        self._theme: ThemeSpec = THEMES["Obsidian Gold"]
        self._use_24h: bool = False
        self._start_ts: float = time.time()
        self._hit_boxes: list[tuple[QRectF, RaidWindow]] = []
        self.setMouseTracking(True)
        self.setMinimumHeight(150)

    def set_data(
        self,
        raids: list[RaidDefinition],
        theme: ThemeSpec,
        use_24h: bool = False,
        now_ts: Optional[float] = None,
    ) -> None:
        self._raids = [r for r in raids if r.enabled]
        self._theme = theme
        self._use_24h = use_24h
        ref = now_ts if now_ts is not None else time.time()
        # Anchor timeline 1 hour before current time so ongoing raids show nicely
        self._start_ts = ref - 3600
        self._windows = build_timeline_windows(self._raids, self._start_ts, hours=24)
        row_h = 30
        needed_h = max(130, 38 + len(self._raids) * row_h + 16)
        self.setMinimumHeight(needed_h)
        self.update()

    def mouseMoveEvent(self, event) -> None:
        pos = event.position()
        for rect, win in self._hit_boxes:
            if rect.contains(pos):
                start_l = format_local_time(win.start_ts, self._use_24h)
                end_l = format_local_time(win.end_ts, self._use_24h)
                start_u = format_utc_time(win.start_ts)
                dur_m = win.duration_sec // 60
                tip = f"{win.raid_name} ({win.phase_label})\nLocal: {start_l} - {end_l}\nStart: {start_u} • {dur_m}m"
                QToolTip.showText(event.globalPosition().toPoint(), tip, self)
                return
        QToolTip.hideText()

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        self._hit_boxes.clear()

        t = self._theme
        w = float(self.width())
        h = float(self.height())
        span_sec = 24.0 * 3600.0
        left_pad = 148.0
        right_pad = 14.0
        top_pad = 28.0
        track_w = max(80.0, w - left_pad - right_pad)
        now_x = left_pad + (3600.0 / span_sec) * track_w

        # Panel frame
        bg_path = QPainterPath()
        bg_path.addRoundedRect(0.5, 0.5, w - 1.0, h - 1.0, 10.0, 10.0)
        painter.fillPath(bg_path, QColor(t.card_bg))
        painter.setPen(QPen(QColor(t.border_subtle), 1.0))
        painter.drawPath(bg_path)

        # Hourly grid every 3 hours
        painter.setFont(QFont("Cascadia Mono", 8))
        start_dt = datetime.fromtimestamp(self._start_ts)
        first_hour_ts = self._start_ts - (start_dt.minute * 60 + start_dt.second) + 3600
        tick_ts = first_hour_ts
        while tick_ts <= self._start_ts + span_sec:
            dt = datetime.fromtimestamp(tick_ts)
            x = left_pad + ((tick_ts - self._start_ts) / span_sec) * track_w
            is_major = (dt.hour % 3 == 0)
            grid_c = QColor(t.border_subtle)
            grid_c.setAlpha(150 if is_major else 55)
            painter.setPen(QPen(grid_c, 1.0))
            painter.drawLine(int(x), int(top_pad - 4), int(x), int(h - 10))
            if is_major and x < w - 34 and abs(x - now_x) >= 30:
                painter.setPen(QColor(t.text_muted))
                lbl = dt.strftime("%H:%M" if self._use_24h else "%I%p").lstrip("0")
                painter.drawText(int(x) - 14, 18, lbl)
            tick_ts += 3600

        # Swimlanes
        row_h = 30.0
        name_font = QFont("Segoe UI", 9, QFont.Weight.Bold)
        fm = painter.fontMetrics()
        for idx, raid in enumerate(self._raids):
            y = top_pad + idx * row_h
            # Alternating lane shade
            if idx % 2 == 0:
                lane_c = QColor(255, 255, 255, 8)
                painter.fillRect(QRectF(8.0, y, w - 16.0, row_h - 4), lane_c)

            painter.setFont(name_font)
            fm = painter.fontMetrics()
            elided_name = fm.elidedText(raid.name, Qt.TextElideMode.ElideRight, int(left_pad - 22))
            painter.setPen(QColor(t.text_primary))
            painter.drawText(
                QRectF(12.0, y, left_pad - 22.0, row_h - 4),
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                elided_name,
            )

            # Event windows for this raid
            for win in self._windows:
                if win.raid_id != raid.id:
                    continue
                ws = max(self._start_ts, win.start_ts)
                we = min(self._start_ts + span_sec, win.end_ts)
                if we <= ws:
                    continue
                x1 = left_pad + ((ws - self._start_ts) / span_sec) * track_w
                x2 = left_pad + ((we - self._start_ts) / span_sec) * track_w
                bw = max(5.0, x2 - x1)
                box = QRectF(x1, y + 4.0, bw, row_h - 12.0)

                base_c = QColor(t.hard_fg if win.is_hard else raid.accent_color)
                fill_c = QColor(base_c)
                fill_c.setAlpha(210 if win.is_hard else 160)
                painter.setPen(QPen(base_c.lighter(120), 1.0))
                painter.setBrush(fill_c)
                painter.drawRoundedRect(box, 3.5, 3.5)
                self._hit_boxes.append((box, win))

        # NOW marker
        now_c = QColor(t.accent_primary)
        painter.setPen(QPen(now_c, 1.8))
        painter.drawLine(int(now_x), int(top_pad - 6), int(now_x), int(h - 6))
        painter.setFont(QFont("Segoe UI", 7, QFont.Weight.Bold))
        painter.setPen(now_c)
        painter.drawText(int(now_x) - 11, int(top_pad - 10), "NOW")

        painter.end()
