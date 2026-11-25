"""
ArcheAge Chronicles - Standalone Raid Timer Overlay
Tracks Crimson Rift and Brutal Nightmare Raid schedules automatically adjusted to local timezone.
Includes Audio Alerts, Custom Sound Support, Configurable Hotkey, Volume Slider, and High-Clarity HUD.

Created by NoYz
"""

import sys
import os
import json
import time
import ctypes
import shutil
from datetime import datetime, timezone, timedelta

from PyQt6.QtCore import Qt, QPoint, QTimer, pyqtSignal, QObject, QUrl
from PyQt6.QtGui import QFont, QColor, QPixmap, QKeySequence, QIcon
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, 
    QLabel, QPushButton, QFrame, QDialog, QComboBox, 
    QCheckBox, QSlider, QFileDialog
)
from PyQt6.QtMultimedia import QSoundEffect, QMediaPlayer, QAudioOutput

# ---------------------------------------------------------
# 1. WINDOWS DPI AWARENESS
# ---------------------------------------------------------
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

# ---------------------------------------------------------
# 2. WIN32 CLICK-THROUGH (WS_EX_TRANSPARENT)
# ---------------------------------------------------------
user32 = ctypes.windll.user32
user32.GetWindowLongPtrW.restype = ctypes.c_longlong
user32.GetWindowLongPtrW.argtypes = [ctypes.c_void_p, ctypes.c_int]
user32.SetWindowLongPtrW.restype = ctypes.c_longlong
user32.SetWindowLongPtrW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_longlong]
GWL_EXSTYLE = -20
WS_EX_LAYERED = 0x00080000
WS_EX_TRANSPARENT = 0x00000020

# Virtual-Key map for clean, hook-free global hotkey detection via GetAsyncKeyState
VK_TABLE = {
    "F1": 0x70, "F2": 0x71, "F3": 0x72, "F4": 0x73,
    "F5": 0x74, "F6": 0x75, "F7": 0x76, "F8": 0x77,
    "F9": 0x78, "F10": 0x79, "F11": 0x7A, "F12": 0x7B,
    "INSERT": 0x2D, "DELETE": 0x2E, "HOME": 0x24, "END": 0x23,
    "PAGE UP": 0x21, "PAGE DOWN": 0x22, "PAUSE": 0x13,
    "SCROLL LOCK": 0x91, "PRINT SCREEN": 0x2C, "NUM LOCK": 0x90,
    "SPACE": 0x20, "TAB": 0x09, "ENTER": 0x0D, "RETURN": 0x0D,
    "BACKSPACE": 0x08, "ESCAPE": 0x1B,
}
for i in range(10):
    VK_TABLE[str(i)] = 0x30 + i
for c in range(ord('A'), ord('Z') + 1):
    VK_TABLE[chr(c)] = c

class HotkeyMonitor(QObject):
    """Native Windows hotkey monitor using GetAsyncKeyState (zero hooks, no keylogger flags)."""
    triggered = pyqtSignal()

    def __init__(self, initial_key="F8", parent=None):
        super().__init__(parent)
        self.current_vk = None
        self._was_down = False
        self.set_key(initial_key)

        self.timer = QTimer(self)
        self.timer.setInterval(40)  # ~25 checks/sec (virtually 0% CPU)
        self.timer.timeout.connect(self._check)
        self.timer.start()

    def set_key(self, key_name):
        if not key_name:
            self.current_vk = None
            return
        k = key_name.strip().upper()
        self.current_vk = VK_TABLE.get(k)
        if not self.current_vk and len(k) == 1:
            self.current_vk = ord(k)

    def _check(self):
        if not self.current_vk:
            return
        is_down = bool(ctypes.windll.user32.GetAsyncKeyState(self.current_vk) & 0x8000)
        if is_down and not self._was_down:
            self.triggered.emit()
        self._was_down = is_down

# ---------------------------------------------------------
# 3. PATHS & CONFIGURATION
# ---------------------------------------------------------
if getattr(sys, 'frozen', False):
    APP_DIR = os.path.dirname(sys.executable)
    RESOURCE_DIR = getattr(sys, '_MEIPASS', APP_DIR)
else:
    APP_DIR = os.path.dirname(os.path.abspath(__file__))
    RESOURCE_DIR = APP_DIR

CONFIG_FILE = os.path.join(APP_DIR, "config.json")
SOUNDS_DIR = os.path.join(APP_DIR, "sounds")
if not os.path.exists(SOUNDS_DIR):
    SOUNDS_DIR = os.path.join(RESOURCE_DIR, "sounds")

CRIMSON_ICON_PATH = os.path.join(SOUNDS_DIR, "crimson_fangs.png")
if not os.path.exists(CRIMSON_ICON_PATH):
    CRIMSON_ICON_PATH = os.path.join(RESOURCE_DIR, "sounds", "crimson_fangs.png")

BUILTIN_SOUNDS = [
    ("viking_horn.wav", "📯 Viking Horn (Default)"),
    ("war_horn.wav", "🎺 Epic War Horn"),
    ("royal_fanfare.wav", "👑 Royal Fanfare"),
    ("crystal_chime.wav", "💎 Crystal Chime"),
    ("temple_gong.wav", "🔔 Temple Gong"),
    ("medieval_bell.wav", "⛪ Medieval Castle Bell"),
    ("tactical_radar.wav", "📡 Tactical Radar Ping"),
    ("battle_drums.wav", "🥁 War Drums"),
    ("phoenix_cry.wav", "🦅 Phoenix Cry"),
    ("fantasy_harp.wav", "🎶 Fantasy Harp"),
    ("thunder_strike.wav", "⚡ Thunder Strike")
]

HOTKEY_PRESETS = [
    "F8", "F1", "F2", "F3", "F4", "F5", "F6", "F7", "F9", "F10", "F11", "F12",
    "Insert", "Delete", "Home", "End", "Page Up", "Page Down", "Pause", "Scroll Lock"
]

def load_config():
    default_cfg = {
        "overlay_pos": {"x": 80, "y": 80},
        "sound_enabled": True,
        "alert_minutes": 5,
        "sound_file": "viking_horn.wav",
        "volume": 50,
        "hotkey": "F8"
    }
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                default_cfg.update(data)
                return default_cfg
        except Exception:
            pass
    return default_cfg

def save_config(cfg):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=4)
    except Exception:
        pass


# Global Sound Player supporting WAV (QSoundEffect) & MP3/OGG (QMediaPlayer)
class SoundManager:
    _effect = None
    _player = None
    _audio_output = None

    @classmethod
    def play(cls, filename_or_path, volume_percent=50):
        if not os.path.isabs(filename_or_path):
            path = os.path.join(SOUNDS_DIR, filename_or_path)
        else:
            path = filename_or_path

        if not os.path.exists(path):
            return

        vol = max(0.0, min(1.0, float(volume_percent) / 100.0))
        try:
            if path.lower().endswith(".wav"):
                if cls._effect is None:
                    cls._effect = QSoundEffect()
                cls._effect.stop()
                cls._effect.setSource(QUrl.fromLocalFile(path))
                cls._effect.setVolume(vol)
                cls._effect.play()
            else:
                if cls._player is None:
                    cls._player = QMediaPlayer()
                    cls._audio_output = QAudioOutput()
                    cls._player.setAudioOutput(cls._audio_output)
                cls._player.stop()
                cls._audio_output.setVolume(vol)
                cls._player.setSource(QUrl.fromLocalFile(path))
                cls._player.play()
        except Exception:
            pass


# ---------------------------------------------------------
# 4. RAID SCHEDULE ENGINE (UTC -> LOCAL CONVERSION & REPEAT)
# ---------------------------------------------------------
# Normal difficulty starts first at scheduled UTC hours.
# Hard difficulty opens immediately after Normal difficulty ends.
# Crimson Rift: Normal 30m, Hard 30m (Total window: 1h)
# Brutal Nightmare: Normal 1h, Hard 1h (Total window: 2h)
CRIMSON_UTC_HOURS = [3, 11, 19]
NIGHTMARE_UTC_HOURS = [4, 12, 20]

def get_raid_windows(raid_type, ref_timestamp=None):
    if ref_timestamp is None:
        ref_timestamp = time.time()

    dt_ref = datetime.fromtimestamp(ref_timestamp, tz=timezone.utc)
    windows = []

    if raid_type == "crimson":
        hours = CRIMSON_UTC_HOURS
        norm_dur = 1800  # 30 minutes
        hard_dur = 1800  # 30 minutes
    else:  # nightmare
        hours = NIGHTMARE_UTC_HOURS
        norm_dur = 3600  # 1 hour (60 minutes)
        hard_dur = 3600  # 1 hour (60 minutes)

    for day_offset in [-1, 0, 1, 2]:
        base_day = (dt_ref + timedelta(days=day_offset)).replace(minute=0, second=0, microsecond=0)
        for h in hours:
            # 1. Normal Difficulty Window
            norm_start_dt = base_day.replace(hour=h)
            norm_start_ts = norm_start_dt.timestamp()
            norm_end_ts = norm_start_ts + norm_dur
            windows.append({
                "difficulty": "Normal",
                "start_ts": norm_start_ts,
                "end_ts": norm_end_ts
            })

            # 2. Hard Difficulty Window (Opens immediately after Normal ends)
            hard_start_ts = norm_end_ts
            hard_end_ts = hard_start_ts + hard_dur
            windows.append({
                "difficulty": "Hard",
                "start_ts": hard_start_ts,
                "end_ts": hard_end_ts
            })

    windows.sort(key=lambda w: w["start_ts"])
    return windows

def get_raid_status(raid_type, current_time=None):
    if current_time is None:
        current_time = time.time()

    windows = get_raid_windows(raid_type, current_time)
    active_window = None
    upcoming_windows = []

    for w in windows:
        if w["start_ts"] <= current_time < w["end_ts"]:
            active_window = w
        elif w["start_ts"] > current_time:
            upcoming_windows.append(w)

    if active_window:
        seconds_left = max(0, int(active_window["end_ts"] - current_time))
        next_win = upcoming_windows[0] if upcoming_windows else None
        return {
            "is_active": True,
            "difficulty": active_window["difficulty"],
            "seconds_left": seconds_left,
            "active_window": active_window,
            "next_window": next_win,
            "upcoming_window": next_win
        }
    else:
        next_win = upcoming_windows[0] if upcoming_windows else None
        following_win = upcoming_windows[1] if len(upcoming_windows) > 1 else None
        seconds_left = max(0, int(next_win["start_ts"] - current_time)) if next_win else 0
        return {
            "is_active": False,
            "difficulty": next_win["difficulty"] if next_win else "Normal",
            "seconds_left": seconds_left,
            "active_window": None,
            "next_window": next_win,
            "upcoming_window": next_win,
            "following_window": following_win
        }

def format_countdown(seconds):
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    return f"{h:02d}:{m:02d}:{s:02d}"

def format_local_time(ts):
    dt = datetime.fromtimestamp(ts)
    return dt.strftime("%I:%M %p").lstrip("0")


# ---------------------------------------------------------
# 5. KEY RECORDER BUTTON WIDGET
# ---------------------------------------------------------
class KeyRecorderButton(QPushButton):
    key_recorded = pyqtSignal(str)

    def __init__(self, current_key="F8", parent=None):
        super().__init__(parent)
        self.current_key = current_key
        self.is_recording = False
        self._update_text()
        self.clicked.connect(self._start_recording)

    def _update_text(self):
        self.setText(f"⌨️ Key: {self.current_key}")
        self.setStyleSheet("""
            QPushButton {
                background: #1C2432;
                color: #00E5FF;
                border: 1px solid #00ADB5;
                border-radius: 4px;
                font-weight: bold;
                padding: 4px 10px;
                font-size: 11px;
            }
            QPushButton:hover {
                background: #00ADB5;
                color: #000;
            }
        """)

    def set_key(self, key_str):
        self.current_key = key_str
        self._update_text()

    def _start_recording(self):
        self.is_recording = True
        self.setText("Press any key...")
        self.setStyleSheet("""
            QPushButton {
                background: #E63946;
                color: #FFFFFF;
                border: 1px solid #FF4C4C;
                border-radius: 4px;
                font-weight: bold;
                padding: 4px 10px;
                font-size: 11px;
            }
        """)
        self.grabKeyboard()

    def keyPressEvent(self, e):
        if self.is_recording:
            key = e.key()
            if key == Qt.Key.Key_Escape:
                self.is_recording = False
                self.releaseKeyboard()
                self._update_text()
                return

            text = QKeySequence(key).toString().strip()
            if not text:
                text = e.text().strip().upper()

            # Normalize key names for the python keyboard library
            key_map = {
                "Ins": "Insert",
                "Del": "Delete",
                "PgUp": "Page Up",
                "PgDown": "Page Down",
                "Return": "Enter",
                "Esc": "Escape"
            }
            text = key_map.get(text, text)

            if text:
                self.current_key = text
                self.key_recorded.emit(text)

            self.is_recording = False
            self.releaseKeyboard()
            self._update_text()
        else:
            super().keyPressEvent(e)


# ---------------------------------------------------------
# 6. SETTINGS DIALOG (CUSTOM SOUNDS + CUSTOMIZABLE HOTKEY)
# ---------------------------------------------------------
class SettingsDialog(QDialog):
    settings_saved = pyqtSignal(dict)

    def __init__(self, cfg, parent=None):
        super().__init__(parent)
        self.cfg = dict(cfg)
        self.setWindowTitle("⚙️ Raid Alert & Hotkey Settings")
        self.setFixedSize(380, 375)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.WindowStaysOnTopHint)
        self.setStyleSheet("""
            QDialog {
                background-color: #12151E;
                color: #FFFFFF;
                font-family: 'Segoe UI';
            }
            QLabel {
                color: #DDD;
                font-size: 11px;
            }
            QComboBox {
                background-color: #1A1F2C;
                color: #EEE;
                border: 1px solid #2D3748;
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 11px;
            }
            QComboBox QAbstractItemView {
                background-color: #161A26;
                color: #FFF;
                selection-background-color: #00ADB5;
            }
            QCheckBox {
                color: #FFF;
                font-size: 11px;
                font-weight: bold;
                spacing: 6px;
            }
            QSlider::groove:horizontal {
                height: 5px;
                background: #252D3D;
                border-radius: 2px;
            }
            QSlider::sub-page:horizontal {
                background: #00ADB5;
                border-radius: 2px;
            }
            QSlider::handle:horizontal {
                background: #00FFF5;
                width: 14px;
                margin-top: -5px;
                margin-bottom: -5px;
                border-radius: 7px;
            }
            QPushButton {
                border-radius: 4px;
                font-size: 11px;
                font-weight: bold;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(9)

        # 1. Enable Sound Checkbox
        self.sound_check = QCheckBox("🔔 Enable Audio Alert Notifications")
        self.sound_check.setChecked(self.cfg.get("sound_enabled", True))
        layout.addWidget(self.sound_check)

        # 2. Timing Selection
        timing_lbl = QLabel("Alert Timing (Before Raid Starts):")
        timing_lbl.setStyleSheet("color: #FFD700; font-weight: bold; font-size: 10px;")
        layout.addWidget(timing_lbl)

        self.timing_combo = QComboBox()
        self.timing_combo.addItem("5 Minutes Before Start", 5)
        self.timing_combo.addItem("10 Minutes Before Start", 10)
        self.timing_combo.addItem("15 Minutes Before Start", 15)
        self.timing_combo.addItem("At Raid Start (Instant)", 0)
        
        cur_min = self.cfg.get("alert_minutes", 5)
        idx = self.timing_combo.findData(cur_min)
        if idx >= 0:
            self.timing_combo.setCurrentIndex(idx)
        layout.addWidget(self.timing_combo)

        # 3. Sound Selection + Custom Sound Feature
        sound_header = QHBoxLayout()
        sound_lbl = QLabel("Alert Sound Effect:")
        sound_lbl.setStyleSheet("color: #00ADB5; font-weight: bold; font-size: 10px;")
        sound_header.addWidget(sound_lbl)
        sound_header.addStretch()

        # Browse Custom Sound Button
        browse_btn = QPushButton("📁 Browse Custom Sound...")
        browse_btn.setFixedSize(145, 22)
        browse_btn.setStyleSheet("""
            QPushButton { background: #1C2432; color: #FFD700; border: 1px solid rgba(255,215,0,0.4); font-size: 10px; }
            QPushButton:hover { background: #FFD700; color: #000; }
        """)
        browse_btn.clicked.connect(self.browse_custom_sound)
        sound_header.addWidget(browse_btn)
        layout.addLayout(sound_header)

        sound_row = QHBoxLayout()
        sound_row.setSpacing(6)

        self.sound_combo = QComboBox()
        cur_file = self.cfg.get("sound_file", "viking_horn.wav")
        
        # Populate built-in presets
        for fname, label in BUILTIN_SOUNDS:
            self.sound_combo.addItem(label, fname)

        # If current sound is a custom sound, add it
        builtin_files = [f[0] for f in BUILTIN_SOUNDS]
        if cur_file not in builtin_files:
            self.sound_combo.addItem(f"📁 Custom: {cur_file}", cur_file)

        idx = self.sound_combo.findData(cur_file)
        if idx >= 0:
            self.sound_combo.setCurrentIndex(idx)
        sound_row.addWidget(self.sound_combo, stretch=3)

        # Test Sound Button
        test_btn = QPushButton("▶ Test")
        test_btn.setFixedSize(55, 26)
        test_btn.setStyleSheet("""
            QPushButton { background: #232B3A; color: #00E5FF; border: 1px solid #00ADB5; }
            QPushButton:hover { background: #00ADB5; color: #000; }
        """)
        test_btn.clicked.connect(self.test_sound)
        sound_row.addWidget(test_btn, stretch=1)
        layout.addLayout(sound_row)

        # 4. Volume Slider (Default 50%)
        vol_header = QHBoxLayout()
        vol_title = QLabel("Playback Volume (Default: 50%):")
        vol_title.setStyleSheet("color: #A0B0C0; font-size: 10px; font-weight: bold;")
        cur_vol = int(self.cfg.get("volume", 50))
        self.vol_value_lbl = QLabel(f"{cur_vol}%")
        self.vol_value_lbl.setStyleSheet("color: #00FFF5; font-size: 11px; font-weight: bold;")
        vol_header.addWidget(vol_title)
        vol_header.addStretch()
        vol_header.addWidget(self.vol_value_lbl)
        layout.addLayout(vol_header)

        self.vol_slider = QSlider(Qt.Orientation.Horizontal)
        self.vol_slider.setRange(0, 100)
        self.vol_slider.setValue(cur_vol)
        self.vol_slider.valueChanged.connect(self._on_vol_changed)
        layout.addWidget(self.vol_slider)

        # 5. Customizable Hotkey
        hotkey_lbl = QLabel("Pass-Through Lock Hotkey (Toggle Click-Through):")
        hotkey_lbl.setStyleSheet("color: #FFB703; font-weight: bold; font-size: 10px;")
        layout.addWidget(hotkey_lbl)

        hotkey_row = QHBoxLayout()
        hotkey_row.setSpacing(6)

        self.hotkey_combo = QComboBox()
        cur_hotkey = self.cfg.get("hotkey", "F8")
        for k in HOTKEY_PRESETS:
            self.hotkey_combo.addItem(k, k)

        # If current hotkey is custom, add it
        if cur_hotkey not in HOTKEY_PRESETS:
            self.hotkey_combo.addItem(cur_hotkey, cur_hotkey)

        h_idx = self.hotkey_combo.findData(cur_hotkey)
        if h_idx >= 0:
            self.hotkey_combo.setCurrentIndex(h_idx)
        self.hotkey_combo.currentIndexChanged.connect(self._on_hotkey_combo_changed)
        hotkey_row.addWidget(self.hotkey_combo, stretch=2)

        # Interactive Key Recorder Button
        self.key_recorder = KeyRecorderButton(current_key=cur_hotkey, parent=self)
        self.key_recorder.key_recorded.connect(self._on_key_recorded)
        hotkey_row.addWidget(self.key_recorder, stretch=2)

        layout.addLayout(hotkey_row)

        layout.addSpacing(4)

        # 6. Save Button (Saves and closes only the dialog)
        save_btn = QPushButton("Save & Close")
        save_btn.setFixedHeight(28)
        save_btn.setStyleSheet("""
            QPushButton { background: #00ADB5; color: #000; border: none; font-weight: bold; font-size: 11px; }
            QPushButton:hover { background: #00FFF5; }
        """)
        save_btn.clicked.connect(self.save_and_close)
        layout.addWidget(save_btn)

    def _on_vol_changed(self, val):
        self.vol_value_lbl.setText(f"{val}%")

    def _on_hotkey_combo_changed(self, idx):
        key = self.hotkey_combo.currentData()
        if key:
            self.key_recorder.set_key(key)

    def _on_key_recorded(self, key):
        # Update combo if not present
        idx = self.hotkey_combo.findData(key)
        if idx < 0:
            self.hotkey_combo.addItem(key, key)
            idx = self.hotkey_combo.count() - 1
        self.hotkey_combo.setCurrentIndex(idx)

    def browse_custom_sound(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Custom Audio File",
            "",
            "Audio Files (*.wav *.mp3 *.ogg *.m4a *.flac);;WAV Files (*.wav);;MP3 Files (*.mp3);;All Files (*.*)"
        )
        if file_path and os.path.exists(file_path):
            dest_name = os.path.basename(file_path)
            dest_path = os.path.join(SOUNDS_DIR, dest_name)
            try:
                if os.path.abspath(file_path) != os.path.abspath(dest_path):
                    shutil.copy2(file_path, dest_path)
            except Exception:
                pass
            
            # Add to combobox and select it
            idx = self.sound_combo.findData(dest_name)
            if idx < 0:
                self.sound_combo.addItem(f"📁 Custom: {dest_name}", dest_name)
                idx = self.sound_combo.count() - 1
            self.sound_combo.setCurrentIndex(idx)

    def test_sound(self):
        fname = self.sound_combo.currentData()
        vol = self.vol_slider.value()
        SoundManager.play(fname, vol)

    def save_and_close(self):
        self.cfg["sound_enabled"] = self.sound_check.isChecked()
        self.cfg["alert_minutes"] = self.timing_combo.currentData()
        self.cfg["sound_file"] = self.sound_combo.currentData()
        self.cfg["volume"] = self.vol_slider.value()
        self.cfg["hotkey"] = self.hotkey_combo.currentData()
        save_config(self.cfg)
        self.settings_saved.emit(self.cfg)
        self.close()


# ---------------------------------------------------------
# 7. HIGH-CLARITY COMPACT RAID CARD
# ---------------------------------------------------------
class HighClarityRaidCard(QFrame):
    def __init__(self, raid_type, title, accent_color, icon_pixmap_path=None, icon_symbol=None, parent=None):
        super().__init__(parent)
        self.raid_type = raid_type
        self.title_text = title
        self.accent_color = accent_color
        self.icon_pixmap_path = icon_pixmap_path
        self.icon_symbol = icon_symbol
        self.init_ui()

    def init_ui(self):
        self.setObjectName("raidCard")
        self.setStyleSheet(f"""
            QFrame#raidCard {{
                background-color: rgba(18, 22, 32, 0.85);
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-left: 3px solid {self.accent_color};
                border-radius: 5px;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(2)

        # Line 1: Icon + Title + Non-Overlapping Fixed Badge
        top_line = QHBoxLayout()
        top_line.setSpacing(6)

        if self.icon_pixmap_path and os.path.exists(self.icon_pixmap_path):
            icon_lbl = QLabel()
            pix = QPixmap(self.icon_pixmap_path).scaled(
                16, 16, 
                Qt.AspectRatioMode.KeepAspectRatio, 
                Qt.TransformationMode.SmoothTransformation
            )
            icon_lbl.setPixmap(pix)
            top_line.addWidget(icon_lbl)
        elif self.icon_symbol:
            icon_lbl = QLabel(self.icon_symbol)
            icon_lbl.setFont(QFont("Segoe UI", 10))
            top_line.addWidget(icon_lbl)

        title_lbl = QLabel(self.title_text)
        title_lbl.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        title_lbl.setStyleSheet(f"color: {self.accent_color}; border: none;")
        top_line.addWidget(title_lbl)

        top_line.addStretch()

        # Fixed-width Status Badge: clearly indicates difficulty & active state
        self.status_badge = QLabel("NORMAL")
        self.status_badge.setFixedWidth(82)
        self.status_badge.setFixedHeight(18)
        self.status_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_badge.setFont(QFont("Segoe UI", 7, QFont.Weight.Bold))
        self.status_badge.setStyleSheet(
            "background-color: #0F2942; color: #38BDF8; "
            "border: 1px solid #0284C7; border-radius: 3px;"
        )
        top_line.addWidget(self.status_badge)
        layout.addLayout(top_line)

        # Line 2: Fixed Action Prefix + Large Countdown + Local Time
        bottom_line = QHBoxLayout()
        bottom_line.setSpacing(6)

        self.action_lbl = QLabel("STARTS IN:")
        self.action_lbl.setFixedWidth(62)
        self.action_lbl.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        self.action_lbl.setStyleSheet("color: #94A3B8; border: none;")
        bottom_line.addWidget(self.action_lbl)

        self.countdown_lbl = QLabel("00:00:00")
        self.countdown_lbl.setFont(QFont("Consolas", 12, QFont.Weight.Bold))
        self.countdown_lbl.setStyleSheet(f"color: {self.accent_color}; border: none;")
        bottom_line.addWidget(self.countdown_lbl)

        bottom_line.addStretch()

        self.local_time_lbl = QLabel("Norm --:-- • Hard --:--")
        self.local_time_lbl.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        self.local_time_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.local_time_lbl.setStyleSheet("color: #64748B; border: none;")
        bottom_line.addWidget(self.local_time_lbl)
        layout.addLayout(bottom_line)

    def update_status(self, status):
        is_active = status["is_active"]
        seconds_left = status["seconds_left"]
        difficulty = status.get("difficulty", "Normal")

        if is_active:
            if difficulty == "Normal":
                # NORMAL ACTIVE (Glowing Green)
                self.status_badge.setText("● NORMAL")
                self.status_badge.setStyleSheet(
                    "background-color: rgba(6, 78, 59, 0.95); color: #00FF88; "
                    "border: 1.5px solid #00FF88; border-radius: 3px; font-weight: bold;"
                )
                self.action_lbl.setText("ENDS IN:")
                self.action_lbl.setStyleSheet("color: #00FF88; font-weight: bold; border: none;")
                self.countdown_lbl.setText(format_countdown(seconds_left))
                self.countdown_lbl.setStyleSheet("color: #00FF88; font-weight: bold; border: none;")

                w = status.get("active_window")
                next_w = status.get("next_window")
                if next_w:
                    self.local_time_lbl.setText(f"Hard starts {format_local_time(next_w['start_ts'])}")
                elif w:
                    self.local_time_lbl.setText(f"Ends {format_local_time(w['end_ts'])}")
                self.local_time_lbl.setStyleSheet("color: #00FF88; font-size: 8px; font-weight: bold; border: none;")
            else:
                # HARD ACTIVE (Glowing Flame Red)
                self.status_badge.setText("● HARD")
                self.status_badge.setStyleSheet(
                    "background-color: rgba(127, 29, 29, 0.95); color: #FF4D4D; "
                    "border: 1.5px solid #FF4D4D; border-radius: 3px; font-weight: bold;"
                )
                self.action_lbl.setText("ENDS IN:")
                self.action_lbl.setStyleSheet("color: #FF4D4D; font-weight: bold; border: none;")
                self.countdown_lbl.setText(format_countdown(seconds_left))
                self.countdown_lbl.setStyleSheet("color: #FF4D4D; font-weight: bold; border: none;")

                w = status.get("active_window")
                if w:
                    self.local_time_lbl.setText(f"Ends {format_local_time(w['end_ts'])}")
                self.local_time_lbl.setStyleSheet("color: #FF4D4D; font-size: 8px; font-weight: bold; border: none;")
        else:
            # UPCOMING STATE - Explicit Difficulty Badge
            if difficulty == "Normal":
                self.status_badge.setText("NORMAL")
                self.status_badge.setStyleSheet(
                    "background-color: #0F2942; color: #38BDF8; "
                    "border: 1px solid #0284C7; border-radius: 3px; font-weight: bold;"
                )
            else:
                self.status_badge.setText("HARD")
                self.status_badge.setStyleSheet(
                    "background-color: #3B1219; color: #FB7185; "
                    "border: 1px solid #E11D48; border-radius: 3px; font-weight: bold;"
                )

            self.action_lbl.setText("STARTS IN:")
            self.action_lbl.setStyleSheet("color: #94A3B8; font-weight: bold; border: none;")
            self.countdown_lbl.setText(format_countdown(seconds_left))
            self.countdown_lbl.setStyleSheet(f"color: {self.accent_color}; font-weight: bold; border: none;")

            # Display both Normal and Hard start times clearly
            next_w = status.get("upcoming_window")
            following_w = status.get("following_window")
            if next_w and following_w:
                t_norm = format_local_time(next_w["start_ts"])
                t_hard = format_local_time(following_w["start_ts"])
                self.local_time_lbl.setText(f"Norm {t_norm} • Hard {t_hard}")
            elif next_w:
                t_next = format_local_time(next_w["start_ts"])
                self.local_time_lbl.setText(f"Starts {t_next}")
            self.local_time_lbl.setStyleSheet("color: #94A3B8; font-size: 8px; font-weight: bold; border: none;")


# ---------------------------------------------------------
# 8. MAIN OVERLAY WINDOW
# ---------------------------------------------------------
class RaidTimerOverlay(QWidget):
    def __init__(self):
        super().__init__()
        self.cfg = load_config()
        self.is_pinned = False
        self.drag_position = QPoint()
        self.settings_dlg = None
        self.triggered_alerts = set()
        self.current_hotkey = self.cfg.get("hotkey", "F8")
        self.hotkey_handler = None

        self.init_ui()
        self.hotkey_monitor = HotkeyMonitor(self.current_hotkey, self)
        self.hotkey_monitor.triggered.connect(self.toggle_pin)
        self._update_hotkey_labels()

        # 1-second update timer
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_all_raids)
        self.timer.start(1000)
        self.update_all_raids()

    def init_ui(self):
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | 
            Qt.WindowType.WindowStaysOnTopHint | 
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFixedSize(360, 142)

        # Window Icon
        icon_path = os.path.join(APP_DIR, "app_icon.ico")
        if not os.path.exists(icon_path):
            icon_path = os.path.join(RESOURCE_DIR, "app_icon.ico")
        if not os.path.exists(icon_path):
            icon_path = os.path.join(SOUNDS_DIR, "app_icon.png")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        # Restore saved position
        pos = self.cfg.get("overlay_pos", {"x": 80, "y": 80})
        self.move(pos.get("x", 80), pos.get("y", 80))

        # Main Card Frame
        self.container = QFrame(self)
        self.container.setGeometry(0, 0, 360, 142)
        self.container.setObjectName("mainFrame")
        self._apply_frame_style(False)

        main_layout = QVBoxLayout(self.container)
        main_layout.setContentsMargins(8, 6, 8, 6)
        main_layout.setSpacing(4)

        # 1. Top Header Row
        header = QHBoxLayout()
        header.setSpacing(4)

        title = QLabel("⚔️ CHRONICLES RAID TIMER")
        title.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        title.setStyleSheet("color: #FFD700; border: none;")
        header.addWidget(title)

        header.addStretch()

        # Settings Button ⚙️
        self.settings_btn = QPushButton("⚙️")
        self.settings_btn.setFixedSize(22, 18)
        self.settings_btn.setStyleSheet("""
            QPushButton { background: rgba(255,255,255,0.08); color: #AAA; border: 1px solid rgba(255,255,255,0.15); border-radius: 3px; font-size: 10px; }
            QPushButton:hover { background: #00ADB5; color: #FFF; }
        """)
        self.settings_btn.setToolTip("Audio Alert & Hotkey Settings")
        self.settings_btn.clicked.connect(self.open_settings)
        header.addWidget(self.settings_btn)

        # Lock / Click-Through Button 📌
        self.pin_btn = QPushButton("📌")
        self.pin_btn.setFixedSize(24, 18)
        self._apply_pin_btn_style(False)
        self.pin_btn.clicked.connect(self.toggle_pin)
        self.pin_btn.setToolTip(f"Toggle Pass-Through Lock [{self.current_hotkey}]")
        header.addWidget(self.pin_btn)

        # Close Button ✕
        close_btn = QPushButton("✕")
        close_btn.setFixedSize(16, 18)
        close_btn.setStyleSheet("""
            QPushButton { background: transparent; color: #777; border: none; font-weight: bold; font-size: 11px; }
            QPushButton:hover { color: #FF4C4C; }
        """)
        close_btn.setToolTip("Close Overlay")
        close_btn.clicked.connect(self.close_app)
        header.addWidget(close_btn)

        main_layout.addLayout(header)

        # 2. Crimson Rift Card (with Beast Fangs Icon)
        self.crimson_card = HighClarityRaidCard(
            raid_type="crimson",
            title="Crimson Rift",
            accent_color="#FF3366",
            icon_pixmap_path=CRIMSON_ICON_PATH,
            parent=self.container
        )
        main_layout.addWidget(self.crimson_card)

        # 3. Brutal Nightmare Card (with Nightmare Crest Icon)
        self.nightmare_card = HighClarityRaidCard(
            raid_type="nightmare",
            title="Brutal Nightmare",
            accent_color="#A855F7",
            icon_symbol="💀",
            parent=self.container
        )
        main_layout.addWidget(self.nightmare_card)

        # 4. Footer Row (Dynamic Lock Mode + Sound Alert Badge + Prominent Creator Credit)
        footer = QHBoxLayout()
        footer.setSpacing(4)

        self.status_badge = QLabel(f"🔓 {self.current_hotkey}: Lock")
        self.status_badge.setFont(QFont("Segoe UI", 7))
        self.status_badge.setStyleSheet("color: #778899; border: none;")
        footer.addWidget(self.status_badge)

        footer.addStretch()

        self.alert_badge = QLabel("🔔 5m")
        self.alert_badge.setFont(QFont("Segoe UI", 7, QFont.Weight.Bold))
        self._update_alert_badge()
        footer.addWidget(self.alert_badge)

        footer.addSpacing(6)

        # Full Creator Credit
        creator_lbl = QLabel("Created by NoYz")
        creator_lbl.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        creator_lbl.setStyleSheet("color: #00ADB5; border: none;")
        footer.addWidget(creator_lbl)

        main_layout.addLayout(footer)

    def apply_hotkey(self, new_key):
        """Binds global hotkey using native GetAsyncKeyState monitor (clean & zero hooks)."""
        if not new_key:
            return
        self.current_hotkey = new_key
        if hasattr(self, 'hotkey_monitor') and self.hotkey_monitor:
            self.hotkey_monitor.set_key(new_key)
        self._update_hotkey_labels()

    def _update_hotkey_labels(self):
        if self.is_pinned:
            self.status_badge.setText(f"🔒 LOCKED [{self.current_hotkey}]")
            self.status_badge.setStyleSheet("color: #00ADB5; font-size: 7px; font-weight: bold; border: none;")
        else:
            self.status_badge.setText(f"🔓 {self.current_hotkey}: Lock")
            self.status_badge.setStyleSheet("color: #778899; font-size: 7px; border: none;")
        self.pin_btn.setToolTip(f"Toggle Pass-Through Lock [{self.current_hotkey}]")

    def _update_alert_badge(self):
        if self.cfg.get("sound_enabled", True):
            m = self.cfg.get("alert_minutes", 5)
            vol = self.cfg.get("volume", 50)
            txt = f"🔔 Start ({vol}%)" if m == 0 else f"🔔 {m}m ({vol}%)"
            self.alert_badge.setText(txt)
            self.alert_badge.setStyleSheet("color: #00E5FF; border: none;")
        else:
            self.alert_badge.setText("🔕 Muted")
            self.alert_badge.setStyleSheet("color: #556677; border: none;")

    def _apply_frame_style(self, locked):
        bg = "rgba(10, 12, 18, 0.88)" if locked else "rgba(14, 17, 24, 0.94)"
        border = "1.5px solid #00ADB5" if locked else "1px solid rgba(255, 215, 0, 0.40)"
        self.container.setStyleSheet(f"""
            QFrame#mainFrame {{
                background-color: {bg};
                border: {border};
                border-radius: 7px;
            }}
        """)

    def _apply_pin_btn_style(self, locked):
        if locked:
            self.pin_btn.setText("🔒")
            self.pin_btn.setStyleSheet("""
                QPushButton { background: #00ADB5; color: #FFF; border: 1px solid #00FFF5; border-radius: 3px; font-size: 10px; font-weight: bold; }
                QPushButton:hover { background: #00FFF5; color: #000; }
            """)
        else:
            self.pin_btn.setText("📌")
            self.pin_btn.setStyleSheet("""
                QPushButton { background: rgba(255, 255, 255, 0.08); color: #FFD700; border: 1px solid rgba(255, 215, 0, 0.4); border-radius: 3px; font-size: 10px; font-weight: bold; }
                QPushButton:hover { background: #FFD700; color: #000; }
            """)

    def toggle_pin(self):
        self.is_pinned = not self.is_pinned
        hwnd = int(self.winId())
        current_style = user32.GetWindowLongPtrW(ctypes.c_void_p(hwnd), GWL_EXSTYLE)

        if self.is_pinned:
            user32.SetWindowLongPtrW(
                ctypes.c_void_p(hwnd),
                GWL_EXSTYLE,
                ctypes.c_longlong(current_style | WS_EX_TRANSPARENT | WS_EX_LAYERED)
            )
            self._apply_frame_style(True)
            self._apply_pin_btn_style(True)
            self.status_badge.setText(f"🔒 LOCKED [{self.current_hotkey}]")
            self.status_badge.setStyleSheet("color: #00ADB5; font-size: 7px; font-weight: bold; border: none;")
        else:
            user32.SetWindowLongPtrW(
                ctypes.c_void_p(hwnd),
                GWL_EXSTYLE,
                ctypes.c_longlong(current_style & ~WS_EX_TRANSPARENT)
            )
            self._apply_frame_style(False)
            self._apply_pin_btn_style(False)
            self.status_badge.setText(f"🔓 {self.current_hotkey}: Lock")
            self.status_badge.setStyleSheet("color: #778899; font-size: 7px; border: none;")

    def open_settings(self):
        if self.is_pinned:
            self.toggle_pin()
        if not self.settings_dlg:
            self.settings_dlg = SettingsDialog(self.cfg, self)
            self.settings_dlg.settings_saved.connect(self.on_settings_saved)
            self.settings_dlg.finished.connect(self._settings_closed)
            self.settings_dlg.show()
        else:
            self.settings_dlg.activateWindow()

    def _settings_closed(self):
        self.settings_dlg = None

    def on_settings_saved(self, new_cfg):
        self.cfg = new_cfg
        new_hotkey = self.cfg.get("hotkey", "F8")
        if new_hotkey != self.current_hotkey:
            self.apply_hotkey(new_hotkey)
        self._update_alert_badge()

    def check_audio_alert(self, raid_name, status, now):
        if not self.cfg.get("sound_enabled", True):
            return

        alert_minutes = self.cfg.get("alert_minutes", 5)
        alert_offset_sec = alert_minutes * 60
        sound_file = self.cfg.get("sound_file", "viking_horn.wav")
        volume = self.cfg.get("volume", 50)

        up_win = status.get("upcoming_window")
        if up_win:
            start_ts = up_win["start_ts"]
            sec_left = int(start_ts - now)
            if 0 <= sec_left <= alert_offset_sec and (alert_offset_sec - sec_left) <= 1:
                key = (raid_name, start_ts, alert_offset_sec)
                if key not in self.triggered_alerts:
                    self.triggered_alerts.add(key)
                    SoundManager.play(sound_file, volume)

    def update_all_raids(self):
        now = time.time()
        crimson_status = get_raid_status("crimson", now)
        nightmare_status = get_raid_status("nightmare", now)

        self.crimson_card.update_status(crimson_status)
        self.nightmare_card.update_status(nightmare_status)

        self.check_audio_alert("crimson", crimson_status, now)
        self.check_audio_alert("nightmare", nightmare_status, now)

        if len(self.triggered_alerts) > 20:
            self.triggered_alerts = {k for k in self.triggered_alerts if now - k[1] < 86400}

    def mousePressEvent(self, e):
        if self.is_pinned:
            return
        if e.button() == Qt.MouseButton.LeftButton:
            self.drag_position = e.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, e):
        if self.is_pinned:
            return
        if e.buttons() == Qt.MouseButton.LeftButton:
            self.move(e.globalPosition().toPoint() - self.drag_position)

    def mouseReleaseEvent(self, e):
        if not self.is_pinned:
            self.cfg["overlay_pos"] = {"x": self.x(), "y": self.y()}
            save_config(self.cfg)

    def close_app(self):
        if hasattr(self, 'hotkey_monitor') and self.hotkey_monitor:
            try:
                self.hotkey_monitor.timer.stop()
            except Exception:
                pass
        if self.settings_dlg:
            try:
                self.settings_dlg.close()
            except Exception:
                pass
        self.cfg["overlay_pos"] = {"x": self.x(), "y": self.y()}
        save_config(self.cfg)
        self.close()
        QApplication.quit()


# ---------------------------------------------------------
# 9. ENTRY POINT
# ---------------------------------------------------------
if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    overlay = RaidTimerOverlay()
    overlay.show()
    sys.exit(app.exec())
