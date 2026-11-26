"""Chronicles Command Center: tabbed dashboard, custom raid creator, audio/TTS, themes & hotkeys."""

from __future__ import annotations

import copy
import json
import os
import re
import shutil
import time
from typing import Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QIcon
from PyQt6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSlider,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from chronicles.audio_engine import (
    BUILTIN_SOUNDS,
    TTS_CALLOUT_STYLES,
    VOICE_PRESETS,
    AudioEngine,
    format_tts_callout,
)
from chronicles.config import (
    AppConfig,
    get_app_root,
    get_config_path,
    get_custom_sounds_dir,
    get_data_dir,
    get_resource_root,
    load_config,
    save_config,
)
from chronicles.models import RaidDefinition, VALID_ICON_KEYS, sample_preset_raids
from chronicles.schedule_engine import (
    build_timeline_windows,
    format_countdown,
    format_local_time,
    format_utc_time,
)
from chronicles.themes import THEMES, ThemeSpec, get_theme
from chronicles.ui.svg_icons import render_svg_icon, render_svg_pixmap
from chronicles.ui.timeline_widget import RaidTimelineWidget
from chronicles.ui.widgets import ColorSwatchButton, KeyCaptureButton
from chronicles.win32_utils import set_windows_startup
from version import APP_AUTHOR, APP_NAME, APP_VERSION

WEEKDAY_LABELS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
MILESTONE_OPTIONS = [15, 10, 5, 3, 1, 0]


class CustomRaidEditorDialog(QDialog):
    """Modal editor for creating or editing a scheduled raid or manual respawn timer."""

    def __init__(
        self,
        theme: ThemeSpec,
        existing: Optional[RaidDefinition] = None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self._theme = theme
        self._existing = existing
        self.result_raid: Optional[RaidDefinition] = None

        self.setWindowTitle("Edit Event Timer" if existing else "Create Custom Raid / Boss Timer")
        self.setFixedSize(460, 520)
        self._build_ui()
        if existing:
            self._populate(existing)

    def _build_ui(self) -> None:
        t = self._theme
        self.setStyleSheet(
            f"""
            QDialog {{ background: {t.bg_primary}; color: {t.text_primary}; font-family: 'Segoe UI'; }}
            QLabel {{ color: {t.text_secondary}; font-size: 11px; }}
            QLineEdit, QComboBox, QSpinBox {{
                background: {t.card_bg}; color: {t.text_primary};
                border: 1px solid {t.border_subtle}; border-radius: 6px; padding: 5px 8px;
                font-size: 11px;
            }}
            QCheckBox {{ background: transparent; color: {t.text_primary}; font-size: 11px; spacing: 8px; }}
            QCheckBox::indicator {{
                width: 15px; height: 15px; border-radius: 4px;
                border: 1.5px solid {t.border_subtle}; background: {t.bg_primary};
            }}
            QCheckBox::indicator:checked {{
                border: 1.5px solid {t.accent_primary}; background: {t.accent_primary};
            }}
            QPushButton {{
                border-radius: 6px; padding: 6px 12px; font-weight: bold; font-size: 11px;
            }}
            """
        )
        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 16)
        root.setSpacing(10)

        hdr = QLabel("Raid / Boss Timer Configuration")
        hdr.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        hdr.setStyleSheet(f"color: {t.accent_primary};")
        root.addWidget(hdr)

        form = QGridLayout()
        form.setSpacing(8)

        form.addWidget(QLabel("Event Name:"), 0, 0)
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("e.g. Black Dragon, Kraken, Guild Siege")
        form.addWidget(self.name_edit, 0, 1)

        form.addWidget(QLabel("Subtitle / Note:"), 1, 0)
        self.sub_edit = QLineEdit()
        self.sub_edit.setPlaceholderText("e.g. World Boss • 30m Window")
        form.addWidget(self.sub_edit, 1, 1)

        form.addWidget(QLabel("Emblem & Accent:"), 2, 0)
        vis_row = QHBoxLayout()
        self.icon_combo = QComboBox()
        for key in VALID_ICON_KEYS:
            self.icon_combo.addItem(render_svg_icon(key, 16, t.text_primary), key.title(), key)
        vis_row.addWidget(self.icon_combo, 1)
        self.color_btn = ColorSwatchButton("#38BDF8", self)
        self.color_btn.clicked.connect(self._pick_color)
        vis_row.addWidget(self.color_btn)
        form.addLayout(vis_row, 2, 1)

        form.addWidget(QLabel("Schedule Type:"), 3, 0)
        self.kind_combo = QComboBox()
        self.kind_combo.addItem("Daily UTC Schedule", "daily_utc")
        self.kind_combo.addItem("Weekly UTC Schedule", "weekly_utc")
        self.kind_combo.addItem("Manual Boss Respawn Countdown", "interval_manual")
        self.kind_combo.currentIndexChanged.connect(self._on_kind_changed)
        form.addWidget(self.kind_combo, 3, 1)

        root.addLayout(form)

        # UTC Times box
        self.times_lbl = QLabel("UTC Start Times (comma-separated HH:MM, e.g. 03:00, 11:00, 19:00):")
        root.addWidget(self.times_lbl)
        self.times_edit = QLineEdit("12:00, 20:00")
        root.addWidget(self.times_edit)

        # Weekdays box
        self.weekdays_box = QWidget()
        wd_lay = QHBoxLayout(self.weekdays_box)
        wd_lay.setContentsMargins(0, 0, 0, 0)
        wd_lay.setSpacing(6)
        self.day_checks: list[QCheckBox] = []
        for idx, name in enumerate(WEEKDAY_LABELS):
            cb = QCheckBox(name)
            cb.setChecked(idx in (1, 3, 5))
            self.day_checks.append(cb)
            wd_lay.addWidget(cb)
        root.addWidget(self.weekdays_box)

        # Respawn interval box
        self.interval_box = QWidget()
        iv_lay = QHBoxLayout(self.interval_box)
        iv_lay.setContentsMargins(0, 0, 0, 0)
        iv_lay.addWidget(QLabel("Respawn Cooldown (Minutes):"))
        self.interval_spin = QSpinBox()
        self.interval_spin.setRange(5, 10080)
        self.interval_spin.setValue(240)
        iv_lay.addWidget(self.interval_spin)
        root.addWidget(self.interval_box)

        # Durations
        dur_grid = QGridLayout()
        dur_grid.setSpacing(8)
        dur_grid.addWidget(QLabel("Phase 1 Duration (min):"), 0, 0)
        self.norm_spin = QSpinBox()
        self.norm_spin.setRange(1, 360)
        self.norm_spin.setValue(30)
        dur_grid.addWidget(self.norm_spin, 0, 1)

        dur_grid.addWidget(QLabel("Phase 1 Label:"), 0, 2)
        self.norm_lbl_edit = QLineEdit("Normal")
        dur_grid.addWidget(self.norm_lbl_edit, 0, 3)

        dur_grid.addWidget(QLabel("Phase 2 / Hard (min, 0=none):"), 1, 0)
        self.hard_spin = QSpinBox()
        self.hard_spin.setRange(0, 360)
        self.hard_spin.setValue(0)
        dur_grid.addWidget(self.hard_spin, 1, 1)

        dur_grid.addWidget(QLabel("Phase 2 Label:"), 1, 2)
        self.hard_lbl_edit = QLineEdit("Hard")
        dur_grid.addWidget(self.hard_lbl_edit, 1, 3)
        root.addLayout(dur_grid)

        root.addStretch(1)

        btns = QHBoxLayout()
        btns.addStretch(1)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setStyleSheet(f"background: {t.card_bg}; color: {t.text_secondary}; border: 1px solid {t.border_subtle};")
        cancel_btn.clicked.connect(self.reject)
        btns.addWidget(cancel_btn)

        save_btn = QPushButton("Save Event")
        save_btn.setStyleSheet(f"background: {t.accent_primary}; color: #0B0E14; border: none;")
        save_btn.clicked.connect(self._on_save)
        btns.addWidget(save_btn)
        root.addLayout(btns)

        self._on_kind_changed()

    def _populate(self, r: RaidDefinition) -> None:
        self.name_edit.setText(r.name)
        self.sub_edit.setText(r.subtitle)
        idx = self.icon_combo.findData(r.icon_key)
        if idx >= 0:
            self.icon_combo.setCurrentIndex(idx)
        self.color_btn.set_color(r.accent_color)
        k_idx = self.kind_combo.findData(r.schedule_kind)
        if k_idx >= 0:
            self.kind_combo.setCurrentIndex(k_idx)
        self.times_edit.setText(", ".join(r.utc_times))
        for i, cb in enumerate(self.day_checks):
            cb.setChecked(i in r.weekdays)
        self.interval_spin.setValue(r.interval_minutes)
        self.norm_spin.setValue(r.normal_duration_min)
        self.hard_spin.setValue(r.hard_duration_min)
        self.norm_lbl_edit.setText(r.normal_label)
        self.hard_lbl_edit.setText(r.hard_label)

        # Keep built-in schedule immutable only in ID, allow editing visuals cleanly
        if r.builtin:
            self.kind_combo.setEnabled(False)
            self.times_edit.setEnabled(False)
            self.norm_spin.setEnabled(False)
            self.hard_spin.setEnabled(False)
        self._on_kind_changed()

    def _on_kind_changed(self) -> None:
        kind = self.kind_combo.currentData()
        is_manual = kind == "interval_manual"
        self.times_lbl.setVisible(not is_manual)
        self.times_edit.setVisible(not is_manual)
        self.weekdays_box.setVisible(kind == "weekly_utc")
        self.interval_box.setVisible(is_manual)

    def _pick_color(self) -> None:
        c = QColorDialog.getColor(QColor(self.color_btn.color_hex), self, "Select Accent Color")
        if c.isValid():
            self.color_btn.set_color(c.name())

    def _on_save(self) -> None:
        name = self.name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "Missing Name", "Please enter an event name.")
            return

        kind = self.kind_combo.currentData()
        times = []
        for raw in self.times_edit.text().split(","):
            s = raw.strip()
            if re.match(r"^\d{1,2}:\d{2}$", s):
                hh, mm = s.split(":")
                times.append(f"{int(hh) % 24:02d}:{int(mm) % 60:02d}")
        if kind != "interval_manual" and not times:
            QMessageBox.warning(self, "Invalid UTC Times", "Enter at least one HH:MM UTC time (e.g. 12:00, 19:30).")
            return

        weekdays = [i for i, cb in enumerate(self.day_checks) if cb.isChecked()]
        if kind == "weekly_utc" and not weekdays:
            QMessageBox.warning(self, "No Weekdays", "Select at least one weekday.")
            return

        rid = self._existing.id if self._existing else re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_") or "custom"
        if not self._existing:
            rid = f"{rid}_{int(time.time()) % 10000}"

        manual_ts = self._existing.manual_target_ts if self._existing else None
        if kind == "interval_manual" and manual_ts is None:
            manual_ts = time.time() + self.interval_spin.value() * 60

        self.result_raid = RaidDefinition(
            id=rid,
            name=name,
            subtitle=self.sub_edit.text().strip() or "Custom Event",
            icon_key=self.icon_combo.currentData(),
            accent_color=self.color_btn.color_hex,
            enabled=self._existing.enabled if self._existing else True,
            builtin=self._existing.builtin if self._existing else False,
            schedule_kind=kind,
            utc_times=times or ["12:00"],
            weekdays=weekdays or [0, 1, 2, 3, 4, 5, 6],
            normal_duration_min=self.norm_spin.value(),
            hard_duration_min=self.hard_spin.value(),
            normal_label=self.norm_lbl_edit.text().strip() or "Normal",
            hard_label=self.hard_lbl_edit.text().strip() or "Hard",
            interval_minutes=self.interval_spin.value(),
            manual_target_ts=manual_ts,
            order=self._existing.order if self._existing else 99,
        )
        self.accept()


class CommandCenterWindow(QWidget):
    """Sidebar-navigated Chronicles Command Center for timeline, raids, audio, themes & hotkeys."""

    config_updated = pyqtSignal(object)
    test_toast_requested = pyqtSignal()

    def __init__(
        self,
        cfg: AppConfig,
        audio_engine: AudioEngine,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.cfg = copy.deepcopy(cfg)
        self.audio = audio_engine
        self.theme: ThemeSpec = get_theme(self.cfg.theme)

        self.setWindowTitle(f"{APP_NAME} — Command Center v{APP_VERSION}")
        self.resize(840, 590)
        self.setMinimumSize(760, 520)

        for candidate in (
            os.path.join(get_resource_root(), "assets", "icons", "app_icon.ico"),
            os.path.join(get_app_root(), "assets", "icons", "app_icon.ico"),
        ):
            if os.path.exists(candidate):
                self.setWindowIcon(QIcon(candidate))
                break

        self._build_ui()
        self._apply_theme_styles()
        self.reload_from_config(self.cfg)

    def _build_ui(self) -> None:
        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Left Navigation Rail
        self.sidebar = QFrame(self)
        self.sidebar.setFixedWidth(210)
        side_lay = QVBoxLayout(self.sidebar)
        side_lay.setContentsMargins(14, 18, 14, 14)
        side_lay.setSpacing(6)

        brand_row = QHBoxLayout()
        brand_row.setSpacing(8)
        self.brand_icon = QLabel()
        self.brand_icon.setFixedSize(28, 28)
        brand_row.addWidget(self.brand_icon)
        brand_txt = QVBoxLayout()
        brand_txt.setSpacing(0)
        self.brand_title = QLabel("CHRONICLES")
        self.brand_title.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        brand_txt.addWidget(self.brand_title)
        self.brand_sub = QLabel(f"Command Center • v{APP_VERSION}")
        self.brand_sub.setFont(QFont("Segoe UI", 8))
        brand_txt.addWidget(self.brand_sub)
        brand_row.addLayout(brand_txt)
        side_lay.addLayout(brand_row)
        side_lay.addSpacing(12)

        self._nav_buttons: list[QPushButton] = []
        nav_items = [
            ("timeline", "Live Timeline"),
            ("sword", "Raids && Custom Events"),
            ("bell", "Alerts, Audio && TTS"),
            ("compact", "HUD && Appearance"),
            ("lock", "Hotkeys && System"),
        ]
        for idx, (ico, label) in enumerate(nav_items):
            btn = QPushButton(f"  {label}")
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFixedHeight(38)
            btn.setProperty("nav_icon", ico)
            btn.clicked.connect(lambda _chk, i=idx: self._switch_tab(i))
            side_lay.addWidget(btn)
            self._nav_buttons.append(btn)

        side_lay.addStretch(1)

        self.credit_lbl = QLabel(f"Developed by {APP_AUTHOR}")
        self.credit_lbl.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        side_lay.addWidget(self.credit_lbl)

        outer.addWidget(self.sidebar)

        # Right Stack Content + Bottom Action Bar
        right_col = QVBoxLayout()
        right_col.setContentsMargins(18, 16, 18, 14)
        right_col.setSpacing(10)

        self.pages = QStackedWidget(self)
        self.pages.addWidget(self._build_timeline_page())
        self.pages.addWidget(self._build_raids_page())
        self.pages.addWidget(self._build_audio_page())
        self.pages.addWidget(self._build_appearance_page())
        self.pages.addWidget(self._build_system_page())
        right_col.addWidget(self.pages, 1)

        bottom_bar = QHBoxLayout()
        bottom_bar.addStretch(1)
        self.apply_btn = QPushButton("Apply Changes")
        self.apply_btn.setFixedHeight(32)
        self.apply_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.apply_btn.clicked.connect(self._apply_changes)
        bottom_bar.addWidget(self.apply_btn)

        self.save_close_btn = QPushButton("Save && Close")
        self.save_close_btn.setFixedHeight(32)
        self.save_close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.save_close_btn.clicked.connect(self._save_and_close)
        bottom_bar.addWidget(self.save_close_btn)
        right_col.addLayout(bottom_bar)

        outer.addLayout(right_col, 1)
        self._switch_tab(0)

    def _wrap_scroll(self, content: QWidget) -> QScrollArea:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(content)
        return scroll

    def _section_title(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        lbl.setProperty("role", "page_title")
        return lbl

    def _card_panel(self) -> tuple[QFrame, QVBoxLayout]:
        card = QFrame()
        card.setProperty("role", "panel")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(8)
        return card, lay

    # ── PAGE 1: LIVE TIMELINE ──
    def _build_timeline_page(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)

        lay.addWidget(self._section_title("24-Hour Raid Timeline & Upcoming Feed"))
        self.timeline_widget = RaidTimelineWidget(page)
        lay.addWidget(self.timeline_widget)

        card, card_lay = self._card_panel()
        hdr = QLabel("Next Scheduled Windows (Local & UTC)")
        hdr.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        card_lay.addWidget(hdr)

        self.feed_list = QListWidget()
        self.feed_list.setMinimumHeight(200)
        card_lay.addWidget(self.feed_list)
        lay.addWidget(card, 1)
        return page

    # ── PAGE 2: RAIDS & CUSTOM EVENTS ──
    def _build_raids_page(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)

        top = QHBoxLayout()
        top.addWidget(self._section_title("Tracked Raids & Custom Events"))
        top.addStretch(1)
        self.add_custom_btn = QPushButton("+ New Custom Event")
        self.add_custom_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.add_custom_btn.clicked.connect(self._create_custom_raid)
        top.addWidget(self.add_custom_btn)
        lay.addLayout(top)

        # Quick Templates Row
        tpl_row = QHBoxLayout()
        tpl_lbl = QLabel("Quick Templates:")
        tpl_row.addWidget(tpl_lbl)
        for preset in sample_preset_raids():
            btn = QPushButton(f"+ {preset.name}")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _chk, p=preset: self._add_preset_raid(p))
            tpl_row.addWidget(btn)
        tpl_row.addStretch(1)
        lay.addLayout(tpl_row)

        self.raids_container = QWidget()
        self.raids_lay = QVBoxLayout(self.raids_container)
        self.raids_lay.setContentsMargins(0, 0, 0, 0)
        self.raids_lay.setSpacing(8)
        lay.addWidget(self._wrap_scroll(self.raids_container), 1)
        return page

    # ── PAGE 3: ALERTS, AUDIO & TTS ──
    def _build_audio_page(self) -> QWidget:
        container = QWidget()
        lay = QVBoxLayout(container)
        lay.setContentsMargins(0, 0, 8, 0)
        lay.setSpacing(10)
        lay.addWidget(self._section_title("Audio Cues, Milestones & Voice Announcer"))

        # Sound Engine Card
        c1, l1 = self._card_panel()
        self.sound_enabled_chk = QCheckBox("Enable Audio Alert Cues")
        l1.addWidget(self.sound_enabled_chk)

        l1.addWidget(QLabel("Alert Milestones (trigger before start):"))
        ms_row = QHBoxLayout()
        self.milestone_checks: dict[int, QCheckBox] = {}
        for m in MILESTONE_OPTIONS:
            lbl = "At Start" if m == 0 else f"{m} min"
            cb = QCheckBox(lbl)
            self.milestone_checks[m] = cb
            ms_row.addWidget(cb)
        ms_row.addStretch(1)
        l1.addLayout(ms_row)

        self.hard_alert_chk = QCheckBox("Also trigger alert when Phase 2 (Hard) begins")
        l1.addWidget(self.hard_alert_chk)

        snd_row = QHBoxLayout()
        self.sound_combo = QComboBox()
        snd_row.addWidget(self.sound_combo, 3)
        browse_snd = QPushButton("Import Custom...")
        browse_snd.setCursor(Qt.CursorShape.PointingHandCursor)
        browse_snd.clicked.connect(self._browse_sound)
        snd_row.addWidget(browse_snd)
        test_snd = QPushButton("Test Sound")
        test_snd.setCursor(Qt.CursorShape.PointingHandCursor)
        test_snd.clicked.connect(self._test_sound)
        snd_row.addWidget(test_snd)
        l1.addLayout(snd_row)

        vol_row = QHBoxLayout()
        vol_row.addWidget(QLabel("Alert Volume:"))
        self.vol_slider = QSlider(Qt.Orientation.Horizontal)
        self.vol_slider.setRange(0, 100)
        self.vol_val_lbl = QLabel("60%")
        self.vol_slider.valueChanged.connect(lambda v: self.vol_val_lbl.setText(f"{v}%"))
        vol_row.addWidget(self.vol_slider, 1)
        vol_row.addWidget(self.vol_val_lbl)
        l1.addLayout(vol_row)
        lay.addWidget(c1)

        # TTS Voice Card
        c2, l2 = self._card_panel()
        self.tts_chk = QCheckBox("Enable Windows Voice Announcer (Text-to-Speech)")
        l2.addWidget(self.tts_chk)

        voice_row = QHBoxLayout()
        voice_row.addWidget(QLabel("Announcer Voice:"))
        self.tts_voice_combo = QComboBox()
        self.tts_voice_combo.currentIndexChanged.connect(self._on_tts_voice_changed)
        voice_row.addWidget(self.tts_voice_combo, 1)
        refresh_voices_btn = QPushButton("Refresh")
        refresh_voices_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        refresh_voices_btn.clicked.connect(self._populate_tts_voices)
        voice_row.addWidget(refresh_voices_btn)
        l2.addLayout(voice_row)

        style_row = QHBoxLayout()
        style_row.addWidget(QLabel("Callout Style:"))
        self.tts_style_combo = QComboBox()
        for style_id, style_lbl in TTS_CALLOUT_STYLES:
            self.tts_style_combo.addItem(style_lbl, style_id)
        style_row.addWidget(self.tts_style_combo, 1)
        test_tts_btn = QPushButton("Test Voice")
        test_tts_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        test_tts_btn.clicked.connect(self._test_tts)
        style_row.addWidget(test_tts_btn)
        l2.addLayout(style_row)

        tts_grid = QGridLayout()
        tts_grid.setSpacing(6)
        tts_grid.addWidget(QLabel("Voice Volume:"), 0, 0)
        self.tts_vol_slider = QSlider(Qt.Orientation.Horizontal)
        self.tts_vol_slider.setRange(0, 100)
        self.tts_vol_lbl = QLabel("75%")
        self.tts_vol_slider.valueChanged.connect(lambda v: self.tts_vol_lbl.setText(f"{v}%"))
        tts_grid.addWidget(self.tts_vol_slider, 0, 1)
        tts_grid.addWidget(self.tts_vol_lbl, 0, 2)

        tts_grid.addWidget(QLabel("Speech Rate:"), 1, 0)
        self.tts_rate_slider = QSlider(Qt.Orientation.Horizontal)
        self.tts_rate_slider.setRange(-40, 40)
        self.tts_rate_lbl = QLabel("0%")
        self.tts_rate_slider.valueChanged.connect(lambda v: self.tts_rate_lbl.setText(f"{v:+d}%"))
        tts_grid.addWidget(self.tts_rate_slider, 1, 1)
        tts_grid.addWidget(self.tts_rate_lbl, 1, 2)

        tts_grid.addWidget(QLabel("Voice Pitch:"), 2, 0)
        self.tts_pitch_slider = QSlider(Qt.Orientation.Horizontal)
        self.tts_pitch_slider.setRange(-40, 40)
        self.tts_pitch_lbl = QLabel("0%")
        self.tts_pitch_slider.valueChanged.connect(lambda v: self.tts_pitch_lbl.setText(f"{v:+d}%"))
        tts_grid.addWidget(self.tts_pitch_slider, 2, 1)
        tts_grid.addWidget(self.tts_pitch_lbl, 2, 2)
        l2.addLayout(tts_grid)
        lay.addWidget(c2)

        # Toast Notification Card
        c3, l3 = self._card_panel()
        self.toast_chk = QCheckBox("Show Non-Intrusive On-Screen Toast Banner")
        l3.addWidget(self.toast_chk)
        pos_row = QHBoxLayout()
        pos_row.addWidget(QLabel("Toast Screen Corner:"))
        self.toast_pos_combo = QComboBox()
        for key, label in [
            ("bottom_right", "Bottom Right"),
            ("top_right", "Top Right"),
            ("bottom_left", "Bottom Left"),
            ("top_left", "Top Left"),
        ]:
            self.toast_pos_combo.addItem(label, key)
        pos_row.addWidget(self.toast_pos_combo, 1)
        preview_toast_btn = QPushButton("Preview Toast")
        preview_toast_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        preview_toast_btn.clicked.connect(self._preview_toast)
        pos_row.addWidget(preview_toast_btn)
        l3.addLayout(pos_row)
        lay.addWidget(c3)

        lay.addStretch(1)
        return self._wrap_scroll(container)

    # ── PAGE 4: HUD & APPEARANCE ──
    def _build_appearance_page(self) -> QWidget:
        container = QWidget()
        lay = QVBoxLayout(container)
        lay.setContentsMargins(0, 0, 8, 0)
        lay.setSpacing(10)
        lay.addWidget(self._section_title("HUD Theme, Layout & Visual Telemetry"))

        # Theme Swatches
        c1, l1 = self._card_panel()
        l1.addWidget(QLabel("Select Glassmorphic Theme:"))
        theme_grid = QGridLayout()
        theme_grid.setSpacing(8)
        self.theme_buttons: dict[str, QPushButton] = {}
        for idx, (t_name, spec) in enumerate(THEMES.items()):
            btn = QPushButton(f"  {t_name}")
            btn.setCheckable(True)
            btn.setFixedHeight(36)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setIcon(render_svg_icon("theme_gem", 16, spec.accent_primary, spec.accent_secondary))
            btn.clicked.connect(lambda _chk, n=t_name: self._select_theme(n))
            theme_grid.addWidget(btn, idx // 2, idx % 2)
            self.theme_buttons[t_name] = btn
        l1.addLayout(theme_grid)
        lay.addWidget(c1)

        # Layout & Sizing
        c2, l2 = self._card_panel()
        grid = QGridLayout()
        grid.setSpacing(8)
        grid.addWidget(QLabel("HUD Display Mode:"), 0, 0)
        self.mode_combo = QComboBox()
        self.mode_combo.addItem("Tactical Cards (Detailed)", "cards")
        self.mode_combo.addItem("Compact Ticker Strip", "compact")
        self.mode_combo.addItem("Horizontal Wide Bar", "horizontal")
        grid.addWidget(self.mode_combo, 0, 1)

        grid.addWidget(QLabel("Text & Icon Scale:"), 1, 0)
        self.scale_combo = QComboBox()
        for label, val in [
            ("75% Mini", 0.75),
            ("85% Compact", 0.85),
            ("100% Standard", 1.0),
            ("115% Large", 1.15),
            ("130% Extra Large", 1.3),
        ]:
            self.scale_combo.addItem(label, val)
        grid.addWidget(self.scale_combo, 1, 1)

        grid.addWidget(QLabel("Unlocked Opacity:"), 2, 0)
        self.op_unlocked = QSlider(Qt.Orientation.Horizontal)
        self.op_unlocked.setRange(45, 100)
        grid.addWidget(self.op_unlocked, 2, 1)

        grid.addWidget(QLabel("Locked Ghost Opacity:"), 3, 0)
        self.op_locked = QSlider(Qt.Orientation.Horizontal)
        self.op_locked.setRange(25, 100)
        grid.addWidget(self.op_locked, 3, 1)
        l2.addLayout(grid)

        self.rings_chk = QCheckBox("Show Radial Progress Rings")
        self.clock_chk = QCheckBox("Show Live Local + UTC Clock in HUD Header")
        self.clock24_chk = QCheckBox("Use 24-Hour Clock Format")
        self.sort_chk = QCheckBox("Auto-Sort Raids (Active && Soonest First)")
        self.snap_chk = QCheckBox("Magnetic Snap to Screen Edges on Drag")
        self.hide_chrome_chk = QCheckBox("Hide Header && Footer in Ghost Lock Mode")
        for cb in (self.rings_chk, self.clock_chk, self.clock24_chk, self.sort_chk, self.snap_chk, self.hide_chrome_chk):
            l2.addWidget(cb)
        lay.addWidget(c2)
        lay.addStretch(1)
        return self._wrap_scroll(container)

    # ── PAGE 5: HOTKEYS & SYSTEM ──
    def _build_system_page(self) -> QWidget:
        container = QWidget()
        lay = QVBoxLayout(container)
        lay.setContentsMargins(0, 0, 8, 0)
        lay.setSpacing(10)
        lay.addWidget(self._section_title("Global Hotkeys, Tray & Configuration"))

        c1, l1 = self._card_panel()
        l1.addWidget(QLabel("Hook-Free Global Hotkeys (Anti-Cheat Safe GetAsyncKeyState):"))
        hk_grid = QGridLayout()
        hk_grid.setSpacing(8)
        self.hk_widgets: dict[str, KeyCaptureButton] = {}
        rows = [
            ("hotkey_lock", "Toggle Ghost Pass-Through Lock:"),
            ("hotkey_toggle_hud", "Show / Hide HUD Overlay:"),
            ("hotkey_compact", "Cycle HUD View Mode:"),
            ("hotkey_snooze", "Snooze Active / Imminent Alert:"),
        ]
        for r_idx, (field_name, label) in enumerate(rows):
            hk_grid.addWidget(QLabel(label), r_idx, 0)
            cap = KeyCaptureButton("", self)
            self.hk_widgets[field_name] = cap
            hk_grid.addWidget(cap, r_idx, 1)
            clr = QPushButton("Clear")
            clr.setFixedWidth(56)
            clr.setCursor(Qt.CursorShape.PointingHandCursor)
            clr.clicked.connect(lambda _chk, w=cap: w.set_binding(""))
            hk_grid.addWidget(clr, r_idx, 2)
        l1.addLayout(hk_grid)
        lay.addWidget(c1)

        c2, l2 = self._card_panel()
        self.tray_chk = QCheckBox("Minimize to System Tray instead of exiting on Hide")
        self.startup_chk = QCheckBox("Launch Chronicles Raid Timer on Windows Startup")
        l2.addWidget(self.tray_chk)
        l2.addWidget(self.startup_chk)
        lay.addWidget(c2)

        c3, l3 = self._card_panel()
        l3.addWidget(QLabel(f"Config Path: {get_config_path()}"))
        io_row = QHBoxLayout()
        for label, slot in [
            ("Open Data Folder", self._open_data_folder),
            ("Export Backup...", self._export_config),
            ("Import Backup...", self._import_config),
            ("Reset Defaults", self._reset_defaults),
        ]:
            b = QPushButton(label)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(slot)
            io_row.addWidget(b)
        l3.addLayout(io_row)

        uninst_row = QHBoxLayout()
        uninst_row.addWidget(QLabel("Program Management:"))
        uninst_row.addStretch(1)
        uninst_btn = QPushButton("Uninstall Chronicles Raid Timer...")
        uninst_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        uninst_btn.setStyleSheet(
            "background: rgba(225, 29, 72, 0.18); color: #FB7185; border: 1px solid #E11D48; border-radius: 7px; padding: 5px 12px;"
        )
        uninst_btn.clicked.connect(self._launch_uninstaller)
        uninst_row.addWidget(uninst_btn)
        l3.addLayout(uninst_row)
        lay.addWidget(c3)
        lay.addStretch(1)
        return self._wrap_scroll(container)

    # ── POPULATE & INTERACTIONS ──
    def reload_from_config(self, cfg: AppConfig) -> None:
        self.cfg = copy.deepcopy(cfg)
        self.theme = get_theme(self.cfg.theme)

        now_ts = time.time()
        self._refresh_timeline(now_ts)
        self._rebuild_raids_list()

        # Audio
        self.sound_enabled_chk.setChecked(self.cfg.sound_enabled)
        for m, cb in self.milestone_checks.items():
            cb.setChecked(m in self.cfg.alert_milestones)
        self.hard_alert_chk.setChecked(self.cfg.alert_on_hard_transition)
        self._populate_sound_combo()
        self.vol_slider.setValue(self.cfg.volume)
        self.vol_val_lbl.setText(f"{self.cfg.volume}%")
        self.tts_chk.setChecked(self.cfg.tts_enabled)
        self._populate_tts_voices(select_id=self.cfg.tts_voice)
        st_idx = self.tts_style_combo.findData(self.cfg.tts_style)
        if st_idx >= 0:
            self.tts_style_combo.setCurrentIndex(st_idx)
        self.tts_vol_slider.setValue(self.cfg.tts_volume)
        self.tts_vol_lbl.setText(f"{self.cfg.tts_volume}%")
        rate_pct = int(round(self.cfg.tts_rate * 100))
        self.tts_rate_slider.setValue(max(-40, min(40, rate_pct)))
        self.tts_rate_lbl.setText(f"{self.tts_rate_slider.value():+d}%")
        pitch_pct = int(round(self.cfg.tts_pitch * 100))
        self.tts_pitch_slider.setValue(max(-40, min(40, pitch_pct)))
        self.tts_pitch_lbl.setText(f"{self.tts_pitch_slider.value():+d}%")
        self.toast_chk.setChecked(self.cfg.toast_enabled)
        t_idx = self.toast_pos_combo.findData(self.cfg.toast_position)
        if t_idx >= 0:
            self.toast_pos_combo.setCurrentIndex(t_idx)

        # Appearance
        self._select_theme(self.cfg.theme, apply_now=False)
        m_idx = self.mode_combo.findData(self.cfg.hud_mode)
        if m_idx >= 0:
            self.mode_combo.setCurrentIndex(m_idx)
        s_idx = min(range(self.scale_combo.count()), key=lambda i: abs(self.scale_combo.itemData(i) - self.cfg.font_scale))
        self.scale_combo.setCurrentIndex(s_idx)
        self.op_unlocked.setValue(int(round(self.cfg.unlocked_opacity * 100)))
        self.op_locked.setValue(int(round(self.cfg.locked_opacity * 100)))
        self.rings_chk.setChecked(self.cfg.show_progress_rings)
        self.clock_chk.setChecked(self.cfg.show_clock)
        self.clock24_chk.setChecked(self.cfg.clock_24h)
        self.sort_chk.setChecked(self.cfg.sort_by_soonest)
        self.snap_chk.setChecked(self.cfg.snap_to_edges)
        self.hide_chrome_chk.setChecked(self.cfg.minimal_hide_chrome_on_lock)

        # Hotkeys & System
        for field_name, widget in self.hk_widgets.items():
            widget.set_binding(getattr(self.cfg, field_name, ""))
        self.tray_chk.setChecked(self.cfg.minimize_to_tray)
        self.startup_chk.setChecked(self.cfg.start_with_windows)
        self._apply_theme_styles()

    def _refresh_timeline(self, now_ts: float) -> None:
        self.timeline_widget.set_data(self.cfg.raids, self.theme, self.cfg.clock_24h, now_ts)
        self.feed_list.clear()
        upcoming = [w for w in build_timeline_windows(self.cfg.raids, now_ts, hours=24) if w.end_ts > now_ts]
        for win in upcoming[:10]:
            if win.start_ts <= now_ts < win.end_ts:
                rel = f"LIVE • ends in {format_countdown(int(win.end_ts - now_ts))}"
            else:
                rel = f"in {format_countdown(int(win.start_ts - now_ts))}"
            txt = (
                f"{win.raid_name} [{win.phase_label}]  —  "
                f"{format_local_time(win.start_ts, self.cfg.clock_24h)} "
                f"({format_utc_time(win.start_ts)})  •  {rel}"
            )
            item = QListWidgetItem(render_svg_icon(win.icon_key, 16, win.accent_color), txt)
            self.feed_list.addItem(item)

    def _rebuild_raids_list(self) -> None:
        while self.raids_lay.count():
            item = self.raids_lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        t = self.theme
        for idx, raid in enumerate(self.cfg.raids):
            card = QFrame()
            card.setProperty("role", "panel")
            row = QHBoxLayout(card)
            row.setContentsMargins(12, 8, 12, 8)
            row.setSpacing(10)

            chk = QCheckBox()
            chk.setChecked(raid.enabled)
            chk.toggled.connect(lambda val, i=idx: self._toggle_raid(i, val))
            row.addWidget(chk)

            ico = QLabel()
            ico.setPixmap(render_svg_pixmap(raid.icon_key, 20, raid.accent_color))
            row.addWidget(ico)

            info = QVBoxLayout()
            info.setSpacing(1)
            title = QLabel(f"{raid.name}" + ("  (Built-in)" if raid.builtin else "  (Custom)"))
            title.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
            info.addWidget(title)
            sched_desc = (
                f"Respawn every {raid.interval_minutes}m"
                if raid.schedule_kind == "interval_manual"
                else f"UTC: {', '.join(raid.utc_times)} • {raid.subtitle}"
            )
            sub = QLabel(sched_desc)
            sub.setStyleSheet(f"color: {t.text_muted}; font-size: 10px;")
            info.addWidget(sub)
            row.addLayout(info, 1)

            sw = ColorSwatchButton(raid.accent_color, card)
            sw.clicked.connect(lambda _c, i=idx: self._pick_raid_color(i))
            row.addWidget(sw)

            edit_b = QPushButton("Edit")
            edit_b.setCursor(Qt.CursorShape.PointingHandCursor)
            edit_b.clicked.connect(lambda _c, i=idx: self._edit_raid(i))
            row.addWidget(edit_b)

            if not raid.builtin:
                del_b = QPushButton("Delete")
                del_b.setCursor(Qt.CursorShape.PointingHandCursor)
                del_b.clicked.connect(lambda _c, i=idx: self._delete_raid(i))
                row.addWidget(del_b)

            self.raids_lay.addWidget(card)
        self.raids_lay.addStretch(1)

    def _toggle_raid(self, idx: int, enabled: bool) -> None:
        if not enabled and sum(1 for r in self.cfg.raids if r.enabled) <= 1:
            self._rebuild_raids_list()
            return
        self.cfg.raids[idx].enabled = enabled

    def _pick_raid_color(self, idx: int) -> None:
        r = self.cfg.raids[idx]
        c = QColorDialog.getColor(QColor(r.accent_color), self, f"{r.name} Accent Color")
        if c.isValid():
            r.accent_color = c.name()
            self._rebuild_raids_list()

    def _edit_raid(self, idx: int) -> None:
        dlg = CustomRaidEditorDialog(self.theme, self.cfg.raids[idx], self)
        if dlg.exec() == QDialog.DialogCode.Accepted and dlg.result_raid:
            self.cfg.raids[idx] = dlg.result_raid
            self._rebuild_raids_list()
            self._refresh_timeline(time.time())

    def _delete_raid(self, idx: int) -> None:
        if len(self.cfg.raids) <= 1:
            return
        self.cfg.raids.pop(idx)
        self._rebuild_raids_list()
        self._refresh_timeline(time.time())

    def _create_custom_raid(self) -> None:
        dlg = CustomRaidEditorDialog(self.theme, None, self)
        if dlg.exec() == QDialog.DialogCode.Accepted and dlg.result_raid:
            dlg.result_raid.order = len(self.cfg.raids)
            self.cfg.raids.append(dlg.result_raid)
            self._rebuild_raids_list()
            self._refresh_timeline(time.time())

    def _add_preset_raid(self, preset: RaidDefinition) -> None:
        existing_ids = {r.id for r in self.cfg.raids}
        clone = copy.deepcopy(preset)
        if clone.id in existing_ids:
            clone.id = f"{clone.id}_{int(time.time()) % 1000}"
        if clone.schedule_kind == "interval_manual":
            clone.manual_target_ts = time.time() + clone.interval_minutes * 60
        clone.order = len(self.cfg.raids)
        self.cfg.raids.append(clone)
        self._rebuild_raids_list()
        self._refresh_timeline(time.time())

    def _populate_sound_combo(self) -> None:
        self.sound_combo.clear()
        for fname, label in BUILTIN_SOUNDS:
            self.sound_combo.addItem(label, fname)
        custom_dir = get_custom_sounds_dir()
        if os.path.exists(custom_dir):
            for fname in sorted(os.listdir(custom_dir)):
                if fname.lower().endswith((".wav", ".mp3", ".ogg", ".flac", ".m4a")):
                    self.sound_combo.addItem(f"Custom: {fname}", fname)
        idx = self.sound_combo.findData(self.cfg.sound_file)
        if idx >= 0:
            self.sound_combo.setCurrentIndex(idx)

    def _browse_sound(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Import Custom Alert Audio", "", "Audio Files (*.wav *.mp3 *.ogg *.flac *.m4a)"
        )
        if path and os.path.exists(path):
            fname = os.path.basename(path)
            dest = os.path.join(get_custom_sounds_dir(), fname)
            if os.path.abspath(path) != os.path.abspath(dest):
                shutil.copy2(path, dest)
            self.cfg.sound_file = fname
            self._populate_sound_combo()

    def _test_sound(self) -> None:
        self.audio.play_sound(self.sound_combo.currentData(), self.vol_slider.value())

    def _populate_tts_voices(self, select_id: Optional[str] = None) -> None:
        target = select_id or self.tts_voice_combo.currentData() or self.cfg.tts_voice
        self.tts_voice_combo.blockSignals(True)
        self.tts_voice_combo.clear()
        for preset in VOICE_PRESETS:
            self.tts_voice_combo.addItem(preset.label, preset.id)
        sys_voices = self.audio.discover_system_voices()
        if sys_voices:
            self.tts_voice_combo.insertSeparator(self.tts_voice_combo.count())
            for sv in sys_voices:
                self.tts_voice_combo.addItem(sv.label, sv.id)
        idx = self.tts_voice_combo.findData(target)
        if idx >= 0:
            self.tts_voice_combo.setCurrentIndex(idx)
        self.tts_voice_combo.blockSignals(False)

    def _on_tts_voice_changed(self) -> None:
        vid = self.tts_voice_combo.currentData() or ""
        preset = AudioEngine.get_preset(vid)
        if preset is not None:
            self.tts_pitch_slider.setValue(int(round(preset.pitch * 100)))
            self.tts_rate_slider.setValue(int(round(preset.rate * 100)))

    def _test_tts(self) -> None:
        style = self.tts_style_combo.currentData() or "standard"
        text = format_tts_callout(
            style,
            title="Crimson Rift",
            message="Normal phase begins in 5 minutes.",
            phase_label="Normal",
            minutes_left=5,
        )
        self.audio.speak(
            text,
            volume_percent=self.tts_vol_slider.value(),
            rate=self.tts_rate_slider.value() / 100.0,
            pitch=self.tts_pitch_slider.value() / 100.0,
            voice_id=self.tts_voice_combo.currentData() or "preset:commander_david",
        )

    def _preview_toast(self) -> None:
        self.cfg.toast_position = self.toast_pos_combo.currentData()
        self.test_toast_requested.emit()

    def _select_theme(self, name: str, apply_now: bool = True) -> None:
        self.cfg.theme = name
        self.theme = get_theme(name)
        for t_name, btn in self.theme_buttons.items():
            btn.setChecked(t_name == name)
        if apply_now:
            self._apply_theme_styles()
            self._refresh_timeline(time.time())

    def _switch_tab(self, idx: int) -> None:
        self.pages.setCurrentIndex(idx)
        t = self.theme
        for i, btn in enumerate(self._nav_buttons):
            checked = (i == idx)
            btn.setChecked(checked)
            ico = btn.property("nav_icon")
            btn.setIcon(render_svg_icon(ico, 16, t.accent_primary if checked else t.text_secondary))
        if idx == 0:
            self._refresh_timeline(time.time())

    def _collect_to_cfg(self) -> AppConfig:
        self.cfg.sound_enabled = self.sound_enabled_chk.isChecked()
        ms = [m for m, cb in self.milestone_checks.items() if cb.isChecked()]
        self.cfg.alert_milestones = sorted(ms, reverse=True) if ms else [5]
        self.cfg.alert_on_hard_transition = self.hard_alert_chk.isChecked()
        self.cfg.sound_file = self.sound_combo.currentData() or "chronicles_horn.wav"
        self.cfg.volume = self.vol_slider.value()
        self.cfg.tts_enabled = self.tts_chk.isChecked()
        self.cfg.tts_voice = self.tts_voice_combo.currentData() or "preset:commander_david"
        self.cfg.tts_style = self.tts_style_combo.currentData() or "standard"
        self.cfg.tts_volume = self.tts_vol_slider.value()
        self.cfg.tts_rate = self.tts_rate_slider.value() / 100.0
        self.cfg.tts_pitch = self.tts_pitch_slider.value() / 100.0
        self.cfg.toast_enabled = self.toast_chk.isChecked()
        self.cfg.toast_position = self.toast_pos_combo.currentData()

        self.cfg.hud_mode = self.mode_combo.currentData()
        self.cfg.font_scale = float(self.scale_combo.currentData())
        self.cfg.unlocked_opacity = self.op_unlocked.value() / 100.0
        self.cfg.locked_opacity = self.op_locked.value() / 100.0
        self.cfg.show_progress_rings = self.rings_chk.isChecked()
        self.cfg.show_clock = self.clock_chk.isChecked()
        self.cfg.clock_24h = self.clock24_chk.isChecked()
        self.cfg.sort_by_soonest = self.sort_chk.isChecked()
        self.cfg.snap_to_edges = self.snap_chk.isChecked()
        self.cfg.minimal_hide_chrome_on_lock = self.hide_chrome_chk.isChecked()

        for field_name, widget in self.hk_widgets.items():
            widget.cancel()
            setattr(self.cfg, field_name, widget.binding)

        self.cfg.minimize_to_tray = self.tray_chk.isChecked()
        prev_startup = self.cfg.start_with_windows
        self.cfg.start_with_windows = self.startup_chk.isChecked()
        if prev_startup != self.cfg.start_with_windows:
            set_windows_startup(self.cfg.start_with_windows)
        return copy.deepcopy(self.cfg)

    def _apply_changes(self) -> None:
        updated = self._collect_to_cfg()
        save_config(updated)
        self.config_updated.emit(updated)

    def _save_and_close(self) -> None:
        self._apply_changes()
        self.hide()

    def _open_data_folder(self) -> None:
        os.startfile(get_data_dir())

    def _export_config(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Export Config Backup", "chronicles_backup.json", "JSON (*.json)")
        if path:
            save_config(self._collect_to_cfg(), path)

    def _import_config(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Import Config Backup", "", "JSON (*.json)")
        if path and os.path.exists(path):
            loaded = load_config(path)
            self.reload_from_config(loaded)
            save_config(loaded)
            self.config_updated.emit(loaded)

    def _reset_defaults(self) -> None:
        fresh = AppConfig()
        self.reload_from_config(fresh)
        save_config(fresh)
        self.config_updated.emit(fresh)

    def _launch_uninstaller(self) -> None:
        from chronicles.ui.uninstaller_wizard import UninstallerWizard

        self._uninst_wiz = UninstallerWizard()
        self._uninst_wiz.show()
        self.hide()

    def _apply_theme_styles(self) -> None:
        t = self.theme
        self.brand_icon.setPixmap(render_svg_pixmap("crest", 26, t.accent_primary, t.accent_secondary))
        self.brand_title.setStyleSheet(f"color: {t.text_primary}; letter-spacing: 1px;")
        self.brand_sub.setStyleSheet(f"color: {t.accent_primary};")
        self.credit_lbl.setStyleSheet(f"color: {t.accent_secondary};")

        for btn in self._nav_buttons:
            ico = btn.property("nav_icon")
            btn.setIcon(render_svg_icon(ico, 16, t.accent_primary if btn.isChecked() else t.text_secondary))

        self.setStyleSheet(
            f"""
            QWidget {{ background: {t.bg_primary}; color: {t.text_primary}; font-family: 'Segoe UI'; }}
            QFrame#sidebar, QFrame {{ background: transparent; }}
            QFrame[role="panel"] {{
                background: {t.card_bg}; border: 1px solid {t.border_subtle}; border-radius: 10px;
            }}
            QLabel[role="page_title"] {{ color: {t.accent_primary}; background: transparent; }}
            QLabel {{ background: transparent; color: {t.text_secondary}; font-size: 11px; }}
            QCheckBox {{ background: transparent; color: {t.text_primary}; font-size: 11px; spacing: 8px; }}
            QCheckBox::indicator {{
                width: 15px; height: 15px; border-radius: 4px;
                border: 1.5px solid {t.border_subtle}; background: {t.bg_primary};
            }}
            QCheckBox::indicator:hover {{
                border: 1.5px solid {t.accent_primary};
            }}
            QCheckBox::indicator:checked {{
                border: 1.5px solid {t.accent_primary}; background: {t.accent_primary};
            }}
            QComboBox {{
                background: {t.bg_elevated}; color: {t.text_primary};
                border: 1px solid {t.border_subtle}; border-radius: 6px; padding: 5px 8px;
            }}
            QListWidget {{
                background: {t.bg_elevated}; color: {t.text_primary};
                border: 1px solid {t.border_subtle}; border-radius: 8px; padding: 4px;
            }}
            QSlider::groove:horizontal {{ height: 5px; background: {t.border_subtle}; border-radius: 2px; }}
            QSlider::sub-page:horizontal {{ background: {t.accent_primary}; border-radius: 2px; }}
            QSlider::handle:horizontal {{
                background: {t.accent_secondary}; width: 14px; margin: -5px 0; border-radius: 7px;
            }}
            QScrollBar:vertical {{
                background: transparent; width: 7px; margin: 2px 0;
            }}
            QScrollBar::handle:vertical {{
                background: {t.border_subtle}; border-radius: 3px; min-height: 24px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: {t.accent_primary};
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
                background: none; height: 0px;
            }}
            QPushButton {{
                background: {t.bg_elevated}; color: {t.text_primary};
                border: 1px solid {t.border_subtle}; border-radius: 7px; padding: 5px 12px; font-weight: bold;
            }}
            QPushButton:hover {{ border: 1px solid {t.accent_primary}; color: {t.accent_primary}; }}
            QPushButton:checked {{
                background: {t.card_hover}; color: {t.accent_primary}; border: 1px solid {t.accent_primary};
            }}
            """
        )
        self.sidebar.setStyleSheet(
            f"background: {t.bg_elevated}; border-right: 1px solid {t.border_subtle};"
        )
        self.apply_btn.setStyleSheet(
            f"background: {t.card_hover}; color: {t.accent_secondary}; border: 1px solid {t.accent_secondary}; border-radius: 7px; padding: 6px 14px;"
        )
        self.save_close_btn.setStyleSheet(
            f"background: {t.accent_primary}; color: #0B0E14; border: none; border-radius: 7px; padding: 6px 16px;"
        )
