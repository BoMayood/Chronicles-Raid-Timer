"""Main glassmorphic Chronicles HUD overlay window."""

from __future__ import annotations

import os
import time
from datetime import datetime, timezone
from typing import Optional

from PyQt6.QtCore import QPoint, QRect, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QIcon, QLinearGradient, QPainter, QPainterPath, QPen
from PyQt6.QtWidgets import (
    QBoxLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMenu,
    QSizeGrip,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from chronicles.config import AppConfig, get_app_root, get_resource_root, save_config
from chronicles.models import RaidStatus
from chronicles.schedule_engine import compute_raid_status
from chronicles.themes import ThemeSpec, get_theme
from chronicles.ui.raid_card import TacticalRaidCard
from chronicles.ui.svg_icons import render_svg_icon, render_svg_pixmap
from chronicles.ui.widgets import SvgIconButton
from chronicles.win32_utils import clamp_to_screens, set_click_through, snap_position_to_edges
from version import APP_SHORT_NAME, APP_VERSION

RESIZE_MARGIN = 8


class ChroniclesHudOverlay(QWidget):
    """Floating frameless glassmorphic HUD overlay with Ghost Lock, resize, and modes."""

    command_center_requested = pyqtSignal()
    snooze_raid_requested = pyqtSignal(str)
    manual_reset_requested = pyqtSignal(str)
    config_changed = pyqtSignal(object)
    hide_to_tray_requested = pyqtSignal()
    quit_requested = pyqtSignal()

    def __init__(self, cfg: AppConfig, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.cfg = cfg
        self.theme: ThemeSpec = get_theme(cfg.theme)
        self.is_locked: bool = False
        self._drag_offset = QPoint()
        self._resize_edge: Optional[str] = None
        self._resize_start_pos = QPoint()
        self._resize_start_geo = QRect()
        self._cards: dict[str, TacticalRaidCard] = {}
        self._latest_statuses: list[RaidStatus] = []
        self._snoozed_until: dict[str, float] = {}
        self._clock_local_str: str = ""
        self._clock_utc_str: str = ""

        self._init_window()
        self._build_ui()
        self.apply_config(self.cfg, resize_fit=False)

    def _init_window(self) -> None:
        self.setWindowTitle(f"{APP_SHORT_NAME} Raid Timer v{APP_VERSION}")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setMouseTracking(True)

        for candidate in (
            os.path.join(get_resource_root(), "assets", "icons", "app_icon.ico"),
            os.path.join(get_app_root(), "assets", "icons", "app_icon.ico"),
        ):
            if os.path.exists(candidate):
                self.setWindowIcon(QIcon(candidate))
                break

        w = max(215, self.cfg.hud_width)
        h = max(90, self.cfg.hud_height)
        x, y = clamp_to_screens(self.cfg.overlay_x, self.cfg.overlay_y, w, h)
        self.resize(w, h)
        self.move(x, y)

    def _build_ui(self) -> None:
        self.root_layout = QVBoxLayout(self)
        self.root_layout.setContentsMargins(9, 7, 9, 6)
        self.root_layout.setSpacing(5)

        # Header Chrome (parent ignores horizontal min-size bloat; children are Fixed so they never overlap)
        self.header_widget = QWidget(self)
        self.header_widget.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        self.header_widget.setMinimumWidth(160)
        header = QHBoxLayout(self.header_widget)
        header.setContentsMargins(2, 0, 2, 0)
        header.setSpacing(5)

        self.crest_lbl = QLabel()
        self.crest_lbl.setFixedSize(19, 19)
        header.addWidget(self.crest_lbl)

        self.title_lbl = QLabel(APP_SHORT_NAME)
        self.title_lbl.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        header.addWidget(self.title_lbl)

        self.ver_pill = QLabel(f"v{APP_VERSION}")
        self.ver_pill.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.ver_pill.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        header.addWidget(self.ver_pill)

        self.clock_lbl = QLabel("")
        self.clock_lbl.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.clock_lbl.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        header.addWidget(self.clock_lbl)

        header.addStretch(1)

        self.mode_btn = SvgIconButton("compact", "Switch HUD Mode (Cards / Compact / Bar)", 21, 13, self)
        self.mode_btn.clicked.connect(self.cycle_hud_mode)
        header.addWidget(self.mode_btn)

        self.mute_btn = SvgIconButton("volume_on", "Quick Mute / Unmute Audio", 21, 13, self)
        self.mute_btn.clicked.connect(self.toggle_mute)
        header.addWidget(self.mute_btn)

        self.cmd_btn = SvgIconButton("settings", "Open Chronicles Command Center", 21, 13, self)
        self.cmd_btn.clicked.connect(self.command_center_requested.emit)
        header.addWidget(self.cmd_btn)

        self.lock_btn = SvgIconButton("unlock", "Toggle Ghost Pass-Through Lock", 21, 13, self)
        self.lock_btn.clicked.connect(self.toggle_lock)
        header.addWidget(self.lock_btn)

        self.hide_btn = SvgIconButton("tray", "Minimize to System Tray", 21, 13, self)
        self.hide_btn.clicked.connect(self.hide_to_tray_requested.emit)
        header.addWidget(self.hide_btn)

        self.close_btn = SvgIconButton("close", "Close Chronicles Raid Timer", 21, 12, self)
        self.close_btn.clicked.connect(self.quit_requested.emit)
        header.addWidget(self.close_btn)

        self.root_layout.addWidget(self.header_widget)

        # Cards Host (dynamically switches TopToBottom vs LeftToRight)
        self.cards_host = QFrame(self)
        self.cards_host.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.cards_layout = QBoxLayout(QBoxLayout.Direction.TopToBottom, self.cards_host)
        self.cards_layout.setContentsMargins(0, 0, 0, 0)
        self.cards_layout.setSpacing(5)
        self.root_layout.addWidget(self.cards_host, 1)

        # Footer Bar (parent ignores horizontal min-size bloat; children are Fixed so they never clip)
        self.footer_widget = QWidget(self)
        self.footer_widget.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        self.footer_widget.setMinimumWidth(160)
        footer = QHBoxLayout(self.footer_widget)
        footer.setContentsMargins(2, 0, 0, 0)
        footer.setSpacing(5)

        self.lock_pill = QLabel()
        self.lock_pill.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lock_pill.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        footer.addWidget(self.lock_pill)

        self.alert_pill = QLabel()
        self.alert_pill.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        footer.addWidget(self.alert_pill)

        footer.addStretch(1)

        self.credit_lbl = QLabel("by NoYz")
        self.credit_lbl.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        footer.addWidget(self.credit_lbl)

        self.size_grip = QSizeGrip(self)
        self.size_grip.setFixedSize(13, 13)
        self.size_grip.setStyleSheet("background: transparent;")
        footer.addWidget(self.size_grip)

        self.root_layout.addWidget(self.footer_widget)

    def set_snoozed_map(self, snoozed_until: dict[str, float]) -> None:
        self._snoozed_until = snoozed_until

    def apply_config(self, cfg: AppConfig, resize_fit: bool = True) -> None:
        self.cfg = cfg
        self.theme = get_theme(cfg.theme)

        direction = (
            QBoxLayout.Direction.LeftToRight
            if cfg.hud_mode == "horizontal"
            else QBoxLayout.Direction.TopToBottom
        )
        self.cards_layout.setDirection(direction)
        self.cards_layout.setSpacing(5 if cfg.hud_mode == "compact" else 6)

        self._sync_card_instances()
        self._style_chrome()
        self.refresh_tick(time.time())
        self._sync_min_size(force_fit=resize_fit)
        self.update()

    def _sync_card_instances(self) -> None:
        active_ids = {r.id for r in self.cfg.raids if r.enabled}
        for rid in list(self._cards.keys()):
            if rid not in active_ids:
                card = self._cards.pop(rid)
                self.cards_layout.removeWidget(card)
                card.deleteLater()

        for raid in self.cfg.raids:
            if not raid.enabled:
                continue
            if raid.id not in self._cards:
                card = TacticalRaidCard(raid.id, self.cards_host)
                card.snooze_requested.connect(self.snooze_raid_requested.emit)
                card.manual_reset_requested.connect(self.manual_reset_requested.emit)
                self._cards[raid.id] = card
                self.cards_layout.addWidget(card)

            card = self._cards[raid.id]
            card.set_theme(self.theme)
            card.set_options(
                mode=self.cfg.hud_mode,
                font_scale=self.cfg.font_scale,
                show_rings=self.cfg.show_progress_rings,
                use_24h=self.cfg.clock_24h,
                locked=self.is_locked,
            )

    def _style_chrome(self) -> None:
        t = self.theme
        s = self.cfg.font_scale

        self.crest_lbl.setPixmap(
            render_svg_pixmap("crest", size=19, color=t.accent_primary, secondary=t.accent_secondary)
        )
        self.title_lbl.setFont(QFont("Segoe UI", max(8, int(round(9.5 * s))), QFont.Weight.Bold))
        self.title_lbl.setStyleSheet(
            f"color: {t.text_primary}; letter-spacing: 1px; background: transparent;"
        )

        self.ver_pill.setFont(QFont("Consolas", max(7, int(round(7.5 * s))), QFont.Weight.Bold))
        self.ver_pill.setStyleSheet(
            f"background: rgba(255,255,255,0.08); color: {t.accent_primary}; "
            f"border: 1px solid {t.border_subtle}; border-radius: 5px; padding: 0px 5px;"
        )

        self.clock_lbl.setFont(QFont("Consolas", max(7, int(round(7.8 * s))), QFont.Weight.Medium))
        self.clock_lbl.setStyleSheet(
            f"color: {t.text_secondary}; background: transparent; padding-left: 2px;"
        )

        mode_icon = "expand" if self.cfg.hud_mode == "compact" else "compact"
        self.mode_btn.configure(
            icon_key=mode_icon,
            fg=t.text_secondary,
            hover_bg="rgba(255,255,255,0.14)",
            border=t.border_subtle,
        )
        self.mute_btn.configure(
            icon_key="volume_on" if self.cfg.sound_enabled else "volume_off",
            fg=t.accent_secondary if self.cfg.sound_enabled else t.text_muted,
            hover_bg="rgba(255,255,255,0.14)",
            border=t.border_subtle,
        )
        self.cmd_btn.configure(
            icon_key="settings",
            fg=t.accent_primary,
            hover_bg="rgba(255,255,255,0.14)",
            border=t.border_subtle,
        )
        self.lock_btn.configure(
            icon_key="lock" if self.is_locked else "unlock",
            fg=t.border_locked if self.is_locked else t.text_secondary,
            hover_bg="rgba(255,255,255,0.14)",
            border=t.border_locked if self.is_locked else t.border_subtle,
            tooltip=f"Toggle Pass-Through Lock [{self.cfg.hotkey_lock or 'None'}]",
        )
        self.hide_btn.configure(
            icon_key="tray",
            fg=t.text_secondary,
            hover_bg="rgba(255,255,255,0.14)",
            border=t.border_subtle,
        )
        self.close_btn.configure(
            icon_key="close",
            fg="#F87171",
            hover_bg="rgba(239,68,68,0.22)",
            border=t.border_subtle,
        )

        # Footer pills & Header responsive fitting based on exact measured pixel budget
        fp = max(6, int(round(7.5 * s)))
        self.lock_pill.setFont(QFont("Segoe UI", fp, QFont.Weight.Bold))
        self.alert_pill.setFont(QFont("Segoe UI", fp, QFont.Weight.Medium))
        self.credit_lbl.setFont(QFont("Segoe UI", fp, QFont.Weight.Bold))
        self.credit_lbl.setStyleSheet(f"color: {t.text_muted}; background: transparent;")
        self._update_responsive_chrome()

    def _update_responsive_chrome(self) -> None:
        t = self.theme
        w = self.width()
        hk = self.cfg.hotkey_lock or "No Key"

        # 1) Measure Header Budget
        btn_count = 6
        buttons_w = btn_count * 21 + (btn_count - 1) * 5
        header_budget = max(0, w - 24 - self.crest_lbl.width() - buttons_w - 10)

        self.title_lbl.setText(APP_SHORT_NAME)
        self.title_lbl.adjustSize()
        title_w = self.title_lbl.sizeHint().width() + 6
        if title_w <= header_budget:
            self.title_lbl.setVisible(True)
            header_budget -= title_w
        else:
            self.title_lbl.setVisible(False)

        self.ver_pill.setText(f"v{APP_VERSION}")
        self.ver_pill.adjustSize()
        ver_w = self.ver_pill.sizeHint().width() + 6
        if ver_w <= header_budget:
            self.ver_pill.setVisible(True)
            header_budget -= ver_w
        else:
            self.ver_pill.setVisible(False)

        if self.cfg.show_clock and self._clock_local_str:
            full_clk = f"{self._clock_local_str} • {self._clock_utc_str} UTC"
            self.clock_lbl.setText(full_clk)
            self.clock_lbl.adjustSize()
            if self.clock_lbl.sizeHint().width() + 6 <= header_budget:
                self.clock_lbl.setVisible(True)
            else:
                self.clock_lbl.setText(self._clock_local_str)
                self.clock_lbl.adjustSize()
                self.clock_lbl.setVisible(self.clock_lbl.sizeHint().width() + 6 <= header_budget)
        else:
            self.clock_lbl.setVisible(False)

        # 2) Measure Footer Budget
        footer_budget = max(0, w - 22 - self.size_grip.width() - 8)

        if self.is_locked:
            lock_candidates = [f"LOCK • {hk}", f"LOCK", hk]
            self.lock_pill.setStyleSheet(
                f"background: rgba(34,211,238,0.14); color: {t.border_locked}; "
                f"border: 1px solid {t.border_locked}; border-radius: 5px; padding: 1px 5px;"
            )
        else:
            lock_candidates = [f"{hk}: Ghost Lock", f"{hk}: Lock", hk]
            self.lock_pill.setStyleSheet(
                f"background: rgba(255,255,255,0.07); color: {t.text_secondary}; "
                f"border: 1px solid {t.border_subtle}; border-radius: 5px; padding: 1px 5px;"
            )

        chosen_lock = lock_candidates[-1]
        for cand in lock_candidates:
            self.lock_pill.setText(cand)
            self.lock_pill.adjustSize()
            if self.lock_pill.sizeHint().width() + 36 <= footer_budget:
                chosen_lock = cand
                break
        self.lock_pill.setText(chosen_lock)
        self.lock_pill.adjustSize()
        footer_budget -= self.lock_pill.sizeHint().width() + 8

        self.credit_lbl.adjustSize()
        credit_w = self.credit_lbl.sizeHint().width() + 8
        if credit_w <= footer_budget:
            self.credit_lbl.setVisible(True)
            footer_budget -= credit_w
        else:
            self.credit_lbl.setVisible(False)

        if self.cfg.sound_enabled:
            ms_txt = ", ".join("Start" if m == 0 else f"{m}m" for m in self.cfg.alert_milestones)
            tts_tag = " • TTS" if self.cfg.tts_enabled else ""
            alert_candidates = [
                f"Alerts: {ms_txt} ({self.cfg.volume}%){tts_tag}",
                f"Alerts: {ms_txt}",
                ms_txt,
            ]
            self.alert_pill.setStyleSheet(f"color: {t.accent_secondary}; background: transparent;")
        else:
            alert_candidates = ["Audio Muted", "Muted"]
            self.alert_pill.setStyleSheet(f"color: {t.text_muted}; background: transparent;")

        alert_shown = False
        for cand in alert_candidates:
            self.alert_pill.setText(cand)
            self.alert_pill.adjustSize()
            if self.alert_pill.sizeHint().width() + 6 <= footer_budget:
                alert_shown = True
                break
        self.alert_pill.setVisible(alert_shown)

        for lbl in (self.title_lbl, self.ver_pill, self.clock_lbl, self.lock_pill, self.alert_pill, self.credit_lbl):
            lbl.updateGeometry()

    def refresh_tick(self, now_ts: Optional[float] = None) -> list[RaidStatus]:
        if now_ts is None:
            now_ts = time.time()

        if self.cfg.show_clock:
            local_dt = datetime.fromtimestamp(now_ts)
            utc_dt = datetime.fromtimestamp(now_ts, tz=timezone.utc)
            self._clock_local_str = local_dt.strftime("%H:%M" if self.cfg.clock_24h else "%I:%M %p").lstrip("0")
            self._clock_utc_str = utc_dt.strftime("%H:%M")
            self._update_responsive_chrome()

        imminent_min = max(self.cfg.alert_milestones) if self.cfg.alert_milestones else 5
        statuses: list[RaidStatus] = []
        for raid in self.cfg.raids:
            if not raid.enabled:
                continue
            snooze_ts = self._snoozed_until.get(raid.id, 0.0)
            st = compute_raid_status(
                raid,
                now_ts=now_ts,
                imminent_minutes=imminent_min,
                snoozed_until_ts=snooze_ts,
            )
            statuses.append(st)

        # Optional automatic priority sort: Active first, then soonest upcoming, then unconfigured
        if self.cfg.sort_by_soonest:
            statuses.sort(
                key=lambda s: (
                    0 if s.is_active else (1 if s.is_configured else 2),
                    s.seconds_left,
                    s.raid.order,
                )
            )

        # Reorder layout items smoothly if order changed
        current_order = [
            self.cards_layout.itemAt(i).widget().raid_id
            for i in range(self.cards_layout.count())
            if isinstance(self.cards_layout.itemAt(i).widget(), TacticalRaidCard)
        ]
        target_order = [s.raid.id for s in statuses]
        if current_order != target_order:
            for st in statuses:
                card = self._cards.get(st.raid.id)
                if card is not None:
                    self.cards_layout.removeWidget(card)
                    self.cards_layout.addWidget(card)

        for st in statuses:
            card = self._cards.get(st.raid.id)
            if card is not None:
                card.update_status(st)

        self._latest_statuses = statuses
        return statuses

    def toggle_lock(self) -> None:
        self.is_locked = not self.is_locked
        set_click_through(int(self.winId()), self.is_locked)

        hide_chrome = self.is_locked and self.cfg.minimal_hide_chrome_on_lock
        self.header_widget.setVisible(not hide_chrome)
        self.footer_widget.setVisible(not hide_chrome)
        self.root_layout.setContentsMargins(
            7 if hide_chrome else 10,
            6 if hide_chrome else 9,
            7 if hide_chrome else 10,
            6 if hide_chrome else 8,
        )

        for card in self._cards.values():
            card.set_options(
                mode=self.cfg.hud_mode,
                font_scale=self.cfg.font_scale,
                show_rings=self.cfg.show_progress_rings,
                use_24h=self.cfg.clock_24h,
                locked=self.is_locked,
            )
        self._style_chrome()

        if self.is_locked:
            self._sync_min_size(force_fit=True)
        else:
            self._sync_min_size(force_fit=False)
            self.resize(
                max(self.cfg.hud_width, self.minimumWidth()),
                max(self.cfg.hud_height, self.minimumHeight()),
            )
        self.update()

    def cycle_hud_mode(self) -> None:
        order = ["cards", "compact", "horizontal"]
        idx = (order.index(self.cfg.hud_mode) + 1) % len(order)
        self.cfg.hud_mode = order[idx]
        save_config(self.cfg)
        self.apply_config(self.cfg, resize_fit=True)
        self.config_changed.emit(self.cfg)

    def toggle_mute(self) -> None:
        self.cfg.sound_enabled = not self.cfg.sound_enabled
        save_config(self.cfg)
        self._style_chrome()
        self.config_changed.emit(self.cfg)

    def _sync_min_size(self, force_fit: bool = False) -> None:
        for card in self._cards.values():
            card._root.activate()
        self.cards_layout.activate()
        self.root_layout.activate()

        visible_cards = [c for c in self._cards.values() if c.isVisible()]
        if self.cfg.hud_mode == "horizontal":
            cards_min_w = sum(c.minimumSizeHint().width() for c in visible_cards) + max(0, len(visible_cards) - 1) * self.cards_layout.spacing()
            min_w = max(460, cards_min_w + 20)
        else:
            cards_min_w = max((c.minimumSizeHint().width() for c in visible_cards), default=205)
            min_w = max(218, cards_min_w + 20)

        min_h = max(40, self.root_layout.minimumSize().height())

        if min_w != self.minimumWidth() or min_h != self.minimumHeight():
            self.setMinimumSize(min_w, min_h)

        if force_fit:
            target_w = min_w if self.cfg.hud_mode == "horizontal" else max(self.cfg.hud_width, min_w)
            self.resize(target_w, min_h)
        else:
            nw = max(self.width(), min_w)
            nh = max(self.height(), min_h)
            if nw != self.width() or nh != self.height():
                self.resize(nw, nh)
        self._style_chrome()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._style_chrome()
        if not self.is_locked and self.isVisible():
            self.cfg.hud_width = self.width()
            self.cfg.hud_height = self.height()

    def _detect_resize_edge(self, pos: QPoint) -> Optional[str]:
        if self.is_locked:
            return None
        r = self.rect()
        near_r = abs(pos.x() - r.width()) <= RESIZE_MARGIN
        near_b = abs(pos.y() - r.height()) <= RESIZE_MARGIN
        if near_r and near_b:
            return "bottom_right"
        if near_r:
            return "right"
        if near_b:
            return "bottom"
        return None

    def mousePressEvent(self, event) -> None:
        if self.is_locked:
            return
        if event.button() == Qt.MouseButton.LeftButton:
            edge = self._detect_resize_edge(event.pos())
            if edge:
                self._resize_edge = edge
                self._resize_start_pos = event.globalPosition().toPoint()
                self._resize_start_geo = self.geometry()
            else:
                self._resize_edge = None
                self._drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
        elif event.button() == Qt.MouseButton.RightButton:
            self._show_context_menu(event.globalPosition().toPoint())

    def mouseMoveEvent(self, event) -> None:
        if self.is_locked:
            return
        if self._resize_edge and (event.buttons() & Qt.MouseButton.LeftButton):
            delta = event.globalPosition().toPoint() - self._resize_start_pos
            orig = self._resize_start_geo
            nw = orig.width()
            nh = orig.height()
            if "right" in self._resize_edge:
                nw = max(self.minimumWidth(), orig.width() + delta.x())
            if "bottom" in self._resize_edge:
                nh = max(self.minimumHeight(), orig.height() + delta.y())
            self.resize(nw, nh)
            return

        edge = self._detect_resize_edge(event.pos())
        if edge == "bottom_right":
            self.setCursor(Qt.CursorShape.SizeFDiagCursor)
        elif edge == "right":
            self.setCursor(Qt.CursorShape.SizeHorCursor)
        elif edge == "bottom":
            self.setCursor(Qt.CursorShape.SizeVerCursor)
        else:
            self.setCursor(Qt.CursorShape.ArrowCursor)

        if event.buttons() == Qt.MouseButton.LeftButton and not self._resize_edge:
            target = event.globalPosition().toPoint() - self._drag_offset
            if self.cfg.snap_to_edges:
                target = snap_position_to_edges(target, self.width(), self.height())
            self.move(target)

    def mouseReleaseEvent(self, event) -> None:
        if not self.is_locked and event.button() == Qt.MouseButton.LeftButton:
            self._resize_edge = None
            self.setCursor(Qt.CursorShape.ArrowCursor)
            self.cfg.overlay_x = self.x()
            self.cfg.overlay_y = self.y()
            self.cfg.hud_width = self.width()
            self.cfg.hud_height = self.height()
            save_config(self.cfg)

    def _show_context_menu(self, global_pos: QPoint) -> None:
        t = self.theme
        menu = QMenu(self)
        menu.setStyleSheet(
            f"""
            QMenu {{
                background-color: {t.bg_elevated};
                color: {t.text_primary};
                border: 1px solid {t.border_subtle};
                border-radius: 8px;
                padding: 5px;
                font-family: 'Segoe UI';
                font-size: 11px;
            }}
            QMenu::item {{
                padding: 6px 14px;
                border-radius: 5px;
            }}
            QMenu::item:selected {{
                background-color: {t.card_hover};
                color: {t.accent_primary};
            }}
            """
        )
        act_cmd = menu.addAction("Open Command Center")
        act_mode = menu.addAction(f"Switch View Mode ({self.cfg.hud_mode.title()})")
        act_lock = menu.addAction(f"Ghost Pass-Through Lock ({self.cfg.hotkey_lock or 'Off'})")
        act_mute = menu.addAction("Unmute Audio" if not self.cfg.sound_enabled else "Mute Audio")
        menu.addSeparator()
        act_hide = menu.addAction("Hide HUD to Tray")
        act_quit = menu.addAction("Quit Chronicles Raid Timer")

        chosen = menu.exec(global_pos)
        if chosen == act_cmd:
            self.command_center_requested.emit()
        elif chosen == act_mode:
            self.cycle_hud_mode()
        elif chosen == act_lock:
            self.toggle_lock()
        elif chosen == act_mute:
            self.toggle_mute()
        elif chosen == act_hide:
            self.hide_to_tray_requested.emit()
        elif chosen == act_quit:
            self.quit_requested.emit()

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        t = self.theme
        w, h = float(self.width()), float(self.height())
        alpha = int(255 * (self.cfg.locked_opacity if self.is_locked else self.cfg.unlocked_opacity))

        path = QPainterPath()
        path.addRoundedRect(0.5, 0.5, w - 1.0, h - 1.0, 14.0, 14.0)

        top_c = QColor(t.bg_elevated)
        top_c.setAlpha(alpha)
        bot_c = QColor(t.bg_primary)
        bot_c.setAlpha(min(255, alpha + 8))

        grad = QLinearGradient(0, 0, 0, h)
        grad.setColorAt(0.0, top_c)
        grad.setColorAt(1.0, bot_c)
        painter.fillPath(path, grad)

        # Top luminous specular rim
        spec_c = QColor(t.specular_top)
        spec_c.setAlpha(110 if not self.is_locked else 70)
        painter.save()
        painter.setClipPath(path)
        painter.setPen(QPen(spec_c, 1.5))
        painter.drawLine(18, 1, int(w) - 18, 1)
        painter.restore()

        # Outer border
        border_c = QColor(t.border_locked if self.is_locked else t.border_subtle)
        border_c.setAlpha(210 if self.is_locked else 185)
        painter.setPen(QPen(border_c, 1.4 if self.is_locked else 1.1))
        painter.drawPath(path)
        painter.end()
