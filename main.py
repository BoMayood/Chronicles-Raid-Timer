"""
ArcheAge Chronicles - Standalone Raid Timer Overlay v1.2.5
Tracks Crimson Rift and Brutal Nightmare Raid schedules automatically adjusted to local timezone.
Includes Audio Alerts, Custom Sound Support, Configurable Hotkey, Volume Slider,
Smooth Resizing (Drag to Resize + Custom Size), Font Scaling, Harmonized Themes,
Custom Raid Colors, Minimal Pass-Through Mode, and High-Clarity HUD.

Created by NoYz
"""

import sys
import os
import json
import time
import ctypes
import shutil
from datetime import datetime, timezone, timedelta

from PyQt6.QtCore import Qt, QPoint, QTimer, pyqtSignal, QObject, QUrl, QSize
from PyQt6.QtGui import QFont, QColor, QPixmap, QKeySequence, QIcon, QCursor
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QFrame, QDialog, QComboBox,
    QCheckBox, QSlider, QFileDialog, QColorDialog, QSizeGrip,
    QSizePolicy
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

# ---------------------------------------------------------
# HARMONIZED THEMES (8 Rich Styles)
# ---------------------------------------------------------
THEMES = {
    "Dark": {
        "frame_bg": "rgba(14, 17, 24, 0.94)",
        "frame_bg_locked": "rgba(10, 12, 18, 0.88)",
        "frame_border": "1.5px solid rgba(255, 215, 0, 0.42)",
        "frame_border_locked": "1.5px solid #00ADB5",
        "card_bg": "rgba(18, 22, 32, 0.88)",
        "card_border": "rgba(255, 255, 255, 0.09)",
        "title_color": "#FFD700",
        "text_color": "#E2E8F0",
        "muted_color": "#94A3B8",
        "accent": "#00ADB5",
        "badge_norm_bg": "#0F2942",
        "badge_norm_fg": "#38BDF8",
        "badge_norm_border": "#0284C7",
        "badge_hard_bg": "#3B1219",
        "badge_hard_fg": "#FB7185",
        "badge_hard_border": "#E11D48",
        "badge_act_norm_bg": "rgba(6, 78, 59, 0.95)",
        "badge_act_norm_fg": "#00FF88",
        "badge_act_hard_bg": "rgba(127, 29, 29, 0.95)",
        "badge_act_hard_fg": "#FF4D4D",
        "footer_color": "#94A3B8",
        "creator_color": "#00ADB5",
        "default_crimson": "#FF3366",
        "default_nightmare": "#A855F7"
    },
    "Crimson": {
        "frame_bg": "rgba(24, 8, 10, 0.95)",
        "frame_bg_locked": "rgba(18, 4, 6, 0.88)",
        "frame_border": "1.5px solid rgba(239, 68, 68, 0.58)",
        "frame_border_locked": "1.5px solid #FF3366",
        "card_bg": "rgba(38, 12, 16, 0.90)",
        "card_border": "rgba(239, 68, 68, 0.22)",
        "title_color": "#FF6B6B",
        "text_color": "#FEE2E2",
        "muted_color": "#FDA4AF",
        "accent": "#FF3366",
        "badge_norm_bg": "#3B1015",
        "badge_norm_fg": "#FCA5A5",
        "badge_norm_border": "#B91C1C",
        "badge_hard_bg": "#500A10",
        "badge_hard_fg": "#FF4D4D",
        "badge_hard_border": "#DC2626",
        "badge_act_norm_bg": "rgba(127, 29, 29, 0.95)",
        "badge_act_norm_fg": "#FF9E9E",
        "badge_act_hard_bg": "rgba(185, 28, 28, 0.95)",
        "badge_act_hard_fg": "#FECACA",
        "footer_color": "#FCA5A5",
        "creator_color": "#FF4D4D",
        "default_crimson": "#FF385C",
        "default_nightmare": "#E11D48"
    },
    "Ocean": {
        "frame_bg": "rgba(6, 16, 28, 0.95)",
        "frame_bg_locked": "rgba(4, 10, 20, 0.88)",
        "frame_border": "1.5px solid rgba(56, 189, 248, 0.55)",
        "frame_border_locked": "1.5px solid #00E5FF",
        "card_bg": "rgba(10, 26, 46, 0.90)",
        "card_border": "rgba(56, 189, 248, 0.20)",
        "title_color": "#38BDF8",
        "text_color": "#E0F2FE",
        "muted_color": "#7DD3FC",
        "accent": "#00E5FF",
        "badge_norm_bg": "#0C2B4E",
        "badge_norm_fg": "#7DD3FC",
        "badge_norm_border": "#0284C7",
        "badge_hard_bg": "#083344",
        "badge_hard_fg": "#22D3EE",
        "badge_hard_border": "#0891B2",
        "badge_act_norm_bg": "rgba(8, 145, 178, 0.95)",
        "badge_act_norm_fg": "#67E8F9",
        "badge_act_hard_bg": "rgba(3, 105, 161, 0.95)",
        "badge_act_hard_fg": "#BAE6FD",
        "footer_color": "#7DD3FC",
        "creator_color": "#00E5FF",
        "default_crimson": "#00E5FF",
        "default_nightmare": "#38BDF8"
    },
    "Forest": {
        "frame_bg": "rgba(8, 22, 12, 0.95)",
        "frame_bg_locked": "rgba(4, 14, 8, 0.88)",
        "frame_border": "1.5px solid rgba(74, 222, 128, 0.55)",
        "frame_border_locked": "1.5px solid #22C55E",
        "card_bg": "rgba(12, 34, 20, 0.90)",
        "card_border": "rgba(74, 222, 128, 0.20)",
        "title_color": "#4ADE80",
        "text_color": "#DCFCE7",
        "muted_color": "#86EFAC",
        "accent": "#22C55E",
        "badge_norm_bg": "#0D2E18",
        "badge_norm_fg": "#86EFAC",
        "badge_norm_border": "#16A34A",
        "badge_hard_bg": "#064E3B",
        "badge_hard_fg": "#34D399",
        "badge_hard_border": "#059669",
        "badge_act_norm_bg": "rgba(22, 101, 52, 0.95)",
        "badge_act_norm_fg": "#86EFAC",
        "badge_act_hard_bg": "rgba(21, 128, 61, 0.95)",
        "badge_act_hard_fg": "#BBF7D0",
        "footer_color": "#86EFAC",
        "creator_color": "#22C55E",
        "default_crimson": "#4ADE80",
        "default_nightmare": "#10B981"
    },
    "Royal Gold": {
        "frame_bg": "rgba(22, 17, 10, 0.95)",
        "frame_bg_locked": "rgba(15, 11, 6, 0.88)",
        "frame_border": "1.5px solid rgba(245, 158, 11, 0.60)",
        "frame_border_locked": "1.5px solid #FBBF24",
        "card_bg": "rgba(34, 26, 14, 0.90)",
        "card_border": "rgba(245, 158, 11, 0.22)",
        "title_color": "#FBBF24",
        "text_color": "#FEF3C7",
        "muted_color": "#FCD34D",
        "accent": "#F59E0B",
        "badge_norm_bg": "#3B280A",
        "badge_norm_fg": "#FDE68A",
        "badge_norm_border": "#D97706",
        "badge_hard_bg": "#451A03",
        "badge_hard_fg": "#FDBA74",
        "badge_hard_border": "#EA580C",
        "badge_act_norm_bg": "rgba(180, 83, 9, 0.95)",
        "badge_act_norm_fg": "#FEF08A",
        "badge_act_hard_bg": "rgba(154, 52, 18, 0.95)",
        "badge_act_hard_fg": "#FED7AA",
        "footer_color": "#FCD34D",
        "creator_color": "#FBBF24",
        "default_crimson": "#FBBF24",
        "default_nightmare": "#F97316"
    },
    "Amethyst": {
        "frame_bg": "rgba(18, 10, 28, 0.95)",
        "frame_bg_locked": "rgba(12, 6, 20, 0.88)",
        "frame_border": "1.5px solid rgba(168, 85, 247, 0.58)",
        "frame_border_locked": "1.5px solid #C084FC",
        "card_bg": "rgba(28, 16, 44, 0.90)",
        "card_border": "rgba(168, 85, 247, 0.22)",
        "title_color": "#C084FC",
        "text_color": "#F3E8FF",
        "muted_color": "#D8B4FE",
        "accent": "#A855F7",
        "badge_norm_bg": "#2E1065",
        "badge_norm_fg": "#D8B4FE",
        "badge_norm_border": "#9333EA",
        "badge_hard_bg": "#4A044E",
        "badge_hard_fg": "#F0ABFC",
        "badge_hard_border": "#C026D3",
        "badge_act_norm_bg": "rgba(107, 33, 168, 0.95)",
        "badge_act_norm_fg": "#E9D5FF",
        "badge_act_hard_bg": "rgba(134, 25, 143, 0.95)",
        "badge_act_hard_fg": "#F5D0FE",
        "footer_color": "#D8B4FE",
        "creator_color": "#C084FC",
        "default_crimson": "#E879F9",
        "default_nightmare": "#A855F7"
    },
    "Cyberpunk": {
        "frame_bg": "rgba(12, 8, 22, 0.95)",
        "frame_bg_locked": "rgba(8, 5, 16, 0.88)",
        "frame_border": "1.5px solid rgba(236, 72, 153, 0.65)",
        "frame_border_locked": "1.5px solid #00FFF5",
        "card_bg": "rgba(20, 14, 36, 0.90)",
        "card_border": "rgba(0, 255, 245, 0.20)",
        "title_color": "#00FFF5",
        "text_color": "#FDF2F8",
        "muted_color": "#F472B6",
        "accent": "#EC4899",
        "badge_norm_bg": "#083344",
        "badge_norm_fg": "#00FFF5",
        "badge_norm_border": "#06B6D4",
        "badge_hard_bg": "#500724",
        "badge_hard_fg": "#FF2A85",
        "badge_hard_border": "#EC4899",
        "badge_act_norm_bg": "rgba(14, 116, 144, 0.95)",
        "badge_act_norm_fg": "#67E8F9",
        "badge_act_hard_bg": "rgba(157, 23, 77, 0.95)",
        "badge_act_hard_fg": "#FBCFE8",
        "footer_color": "#00FFF5",
        "creator_color": "#EC4899",
        "default_crimson": "#FF2A85",
        "default_nightmare": "#00FFF5"
    },
    "Minimal Glass": {
        "frame_bg": "rgba(20, 24, 31, 0.82)",
        "frame_bg_locked": "rgba(15, 18, 24, 0.72)",
        "frame_border": "1.5px solid rgba(255, 255, 255, 0.25)",
        "frame_border_locked": "1.5px solid rgba(255, 255, 255, 0.45)",
        "card_bg": "rgba(255, 255, 255, 0.06)",
        "card_border": "rgba(255, 255, 255, 0.14)",
        "title_color": "#F8FAFC",
        "text_color": "#F1F5F9",
        "muted_color": "#CBD5E1",
        "accent": "#E2E8F0",
        "badge_norm_bg": "rgba(255, 255, 255, 0.10)",
        "badge_norm_fg": "#F8FAFC",
        "badge_norm_border": "rgba(255, 255, 255, 0.30)",
        "badge_hard_bg": "rgba(248, 113, 113, 0.18)",
        "badge_hard_fg": "#FCA5A5",
        "badge_hard_border": "#EF4444",
        "badge_act_norm_bg": "rgba(16, 185, 129, 0.30)",
        "badge_act_norm_fg": "#6EE7B7",
        "badge_act_hard_bg": "rgba(239, 68, 68, 0.35)",
        "badge_act_hard_fg": "#FCA5A5",
        "footer_color": "#CBD5E1",
        "creator_color": "#F8FAFC",
        "default_crimson": "#F8FAFC",
        "default_nightmare": "#CBD5E1"
    },
}

FONT_SCALE_OPTIONS = [
    ("Small (90%)", 0.9),
    ("Normal (100%)", 1.0),
    ("Large (115%)", 1.15),
    ("Extra Large (130%)", 1.3),
]

MIN_WINDOW_W = 340
MIN_WINDOW_H = 138
MINIMAL_WINDOW_H = 92
RESIZE_MARGIN = 8


def load_config():
    default_cfg = {
        "overlay_pos": {"x": 80, "y": 80},
        "sound_enabled": True,
        "alert_minutes": 5,
        "sound_file": "viking_horn.wav",
        "volume": 50,
        "hotkey": "F8",
        "theme": "Dark",
        "font_scale": 1.0,
        "win_width": 400,
        "win_height": 165,
        "crimson_color": "#FF3366",
        "nightmare_color": "#A855F7",
        "show_crimson": True,
        "show_nightmare": True,
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
        norm_dur = 3600  # 1 hour
        hard_dur = 3600  # 1 hour

    for day_offset in [-1, 0, 1, 2]:
        base_day = (dt_ref + timedelta(days=day_offset)).replace(minute=0, second=0, microsecond=0)
        for h in hours:
            norm_start_dt = base_day.replace(hour=h)
            norm_start_ts = norm_start_dt.timestamp()
            norm_end_ts = norm_start_ts + norm_dur
            windows.append({
                "difficulty": "Normal",
                "start_ts": norm_start_ts,
                "end_ts": norm_end_ts
            })

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

            key_map = {
                "Ins": "Insert",
                "Del": "Delete",
                "PgUp": "Page Up",
                "PgDown": "Page Down",
                "Return": "Enter",
                "Esc": "Escape",
                "ScrollLock": "Scroll Lock",
                "NumLock": "Num Lock",
                "Print": "Print Screen",
                "Space": "Space"
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

    def cancel_recording(self):
        if self.is_recording:
            self.is_recording = False
            self.releaseKeyboard()
            self._update_text()


# ---------------------------------------------------------
# 6. SETTINGS DIALOG
# ---------------------------------------------------------
class SettingsDialog(QDialog):
    settings_saved = pyqtSignal(dict)

    def __init__(self, cfg, parent=None):
        super().__init__(parent)
        self.cfg = dict(cfg)
        self.setWindowTitle("⚙️ Raid Timer Settings")
        self.setFixedSize(410, 620)
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
        layout.setContentsMargins(18, 12, 18, 12)
        layout.setSpacing(7)

        # ── AUDIO SECTION ──
        section_audio = QLabel("🔊 AUDIO SETTINGS")
        section_audio.setStyleSheet("color: #FFD700; font-weight: bold; font-size: 10px; border: none;")
        layout.addWidget(section_audio)

        self.sound_check = QCheckBox("🔔 Enable Audio Alert Notifications")
        self.sound_check.setChecked(self.cfg.get("sound_enabled", True))
        layout.addWidget(self.sound_check)

        timing_lbl = QLabel("Alert Timing (Before Raid Starts):")
        timing_lbl.setStyleSheet("color: #A0B0C0; font-weight: bold; font-size: 10px;")
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

        sound_header = QHBoxLayout()
        sound_lbl = QLabel("Alert Sound Effect:")
        sound_lbl.setStyleSheet("color: #00ADB5; font-weight: bold; font-size: 10px;")
        sound_header.addWidget(sound_lbl)
        sound_header.addStretch()

        browse_btn = QPushButton("📁 Browse...")
        browse_btn.setFixedSize(90, 22)
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

        for fname, label in BUILTIN_SOUNDS:
            self.sound_combo.addItem(label, fname)

        builtin_files = [f[0] for f in BUILTIN_SOUNDS]
        if cur_file not in builtin_files:
            self.sound_combo.addItem(f"📁 Custom: {cur_file}", cur_file)

        idx = self.sound_combo.findData(cur_file)
        if idx >= 0:
            self.sound_combo.setCurrentIndex(idx)
        sound_row.addWidget(self.sound_combo, stretch=3)

        test_btn = QPushButton("▶ Test")
        test_btn.setFixedSize(55, 26)
        test_btn.setStyleSheet("""
            QPushButton { background: #232B3A; color: #00E5FF; border: 1px solid #00ADB5; }
            QPushButton:hover { background: #00ADB5; color: #000; }
        """)
        test_btn.clicked.connect(self.test_sound)
        sound_row.addWidget(test_btn, stretch=1)
        layout.addLayout(sound_row)

        vol_header = QHBoxLayout()
        vol_title = QLabel("Volume:")
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

        # ── HOTKEY SECTION ──
        section_hotkey = QLabel("⌨️ HOTKEY")
        section_hotkey.setStyleSheet("color: #FFD700; font-weight: bold; font-size: 10px; border: none; margin-top: 3px;")
        layout.addWidget(section_hotkey)

        hotkey_lbl = QLabel("Pass-Through Lock Hotkey:")
        hotkey_lbl.setStyleSheet("color: #FFB703; font-weight: bold; font-size: 10px;")
        layout.addWidget(hotkey_lbl)

        hotkey_row = QHBoxLayout()
        hotkey_row.setSpacing(6)

        self.hotkey_combo = QComboBox()
        cur_hotkey = self.cfg.get("hotkey", "F8")
        for k in HOTKEY_PRESETS:
            self.hotkey_combo.addItem(k, k)

        if cur_hotkey not in HOTKEY_PRESETS:
            self.hotkey_combo.addItem(cur_hotkey, cur_hotkey)

        h_idx = self.hotkey_combo.findData(cur_hotkey)
        if h_idx >= 0:
            self.hotkey_combo.setCurrentIndex(h_idx)
        self.hotkey_combo.currentIndexChanged.connect(self._on_hotkey_combo_changed)
        hotkey_row.addWidget(self.hotkey_combo, stretch=2)

        self.key_recorder = KeyRecorderButton(current_key=cur_hotkey, parent=self)
        self.key_recorder.key_recorded.connect(self._on_key_recorded)
        hotkey_row.addWidget(self.key_recorder, stretch=2)

        layout.addLayout(hotkey_row)

        # ── APPEARANCE & SIZING SECTION ──
        section_appear = QLabel("🎨 APPEARANCE & SIZING")
        section_appear.setStyleSheet("color: #FFD700; font-weight: bold; font-size: 10px; border: none; margin-top: 3px;")
        layout.addWidget(section_appear)

        # Theme Selector
        theme_row = QHBoxLayout()
        theme_lbl = QLabel("HUD Theme:")
        theme_lbl.setStyleSheet("color: #A0B0C0; font-weight: bold; font-size: 10px;")
        theme_row.addWidget(theme_lbl)
        self.theme_combo = QComboBox()
        for name in THEMES.keys():
            self.theme_combo.addItem(name, name)
        cur_theme = self.cfg.get("theme", "Dark")
        t_idx = self.theme_combo.findData(cur_theme)
        if t_idx >= 0:
            self.theme_combo.setCurrentIndex(t_idx)
        theme_row.addWidget(self.theme_combo, stretch=1)
        layout.addLayout(theme_row)

        # Font Size Selector (User request: تكبير خط الكتابة)
        font_row = QHBoxLayout()
        font_lbl = QLabel("Text / Font Size:")
        font_lbl.setStyleSheet("color: #A0B0C0; font-weight: bold; font-size: 10px;")
        font_row.addWidget(font_lbl)
        self.font_combo = QComboBox()
        cur_fscale = self.cfg.get("font_scale", 1.0)
        for label, val in FONT_SCALE_OPTIONS:
            self.font_combo.addItem(label, val)
        f_idx = next((i for i, (_, v) in enumerate(FONT_SCALE_OPTIONS) if abs(v - cur_fscale) < 0.05), 1)
        self.font_combo.setCurrentIndex(f_idx)
        font_row.addWidget(self.font_combo, stretch=1)
        layout.addLayout(font_row)

        # Custom Raid Colors
        color_row = QHBoxLayout()
        color_row.setSpacing(8)

        cr_lbl = QLabel("Crimson Color:")
        cr_lbl.setStyleSheet("color: #A0B0C0; font-weight: bold; font-size: 10px;")
        color_row.addWidget(cr_lbl)

        self._crimson_color = self.cfg.get("crimson_color", "#FF3366")
        self.crimson_color_btn = QPushButton("")
        self.crimson_color_btn.setFixedSize(28, 20)
        self._apply_color_btn(self.crimson_color_btn, self._crimson_color)
        self.crimson_color_btn.clicked.connect(self._pick_crimson_color)
        color_row.addWidget(self.crimson_color_btn)

        color_row.addSpacing(6)

        nm_lbl = QLabel("Nightmare Color:")
        nm_lbl.setStyleSheet("color: #A0B0C0; font-weight: bold; font-size: 10px;")
        color_row.addWidget(nm_lbl)

        self._nightmare_color = self.cfg.get("nightmare_color", "#A855F7")
        self.nightmare_color_btn = QPushButton("")
        self.nightmare_color_btn.setFixedSize(28, 20)
        self._apply_color_btn(self.nightmare_color_btn, self._nightmare_color)
        self.nightmare_color_btn.clicked.connect(self._pick_nightmare_color)
        color_row.addWidget(self.nightmare_color_btn)

        color_row.addStretch()
        layout.addLayout(color_row)

        # ── VISIBLE RAIDS SECTION ──
        section_raids = QLabel("👁️ VISIBLE RAIDS")
        section_raids.setStyleSheet("color: #FFD700; font-weight: bold; font-size: 10px; border: none; margin-top: 3px;")
        layout.addWidget(section_raids)

        raids_row = QHBoxLayout()
        raids_row.setSpacing(12)
        self.show_crimson_check = QCheckBox("Show Crimson Rift")
        self.show_crimson_check.setChecked(self.cfg.get("show_crimson", True))
        self.show_crimson_check.toggled.connect(self._on_raid_toggle)
        raids_row.addWidget(self.show_crimson_check)

        self.show_nightmare_check = QCheckBox("Show Brutal Nightmare")
        self.show_nightmare_check.setChecked(self.cfg.get("show_nightmare", True))
        self.show_nightmare_check.toggled.connect(self._on_raid_toggle)
        raids_row.addWidget(self.show_nightmare_check)
        raids_row.addStretch()
        layout.addLayout(raids_row)

        # Window Resize Info Tip
        resize_hint = QLabel("💡 Tip: Drag window edges or bottom-right corner to freely resize!")
        resize_hint.setStyleSheet("color: #00ADB5; font-size: 9px; font-style: italic;")
        layout.addWidget(resize_hint)

        layout.addSpacing(2)

        # Save Button
        save_btn = QPushButton("Save & Close")
        save_btn.setFixedHeight(28)
        save_btn.setStyleSheet("""
            QPushButton { background: #00ADB5; color: #000; border: none; font-weight: bold; font-size: 11px; }
            QPushButton:hover { background: #00FFF5; }
        """)
        save_btn.clicked.connect(self.save_and_close)
        layout.addWidget(save_btn)

    def _apply_color_btn(self, btn, color):
        btn.setStyleSheet(f"""
            QPushButton {{
                background: {color};
                border: 2px solid #555;
                border-radius: 4px;
            }}
            QPushButton:hover {{
                border: 2px solid #FFF;
            }}
        """)

    def _pick_crimson_color(self):
        color = QColorDialog.getColor(QColor(self._crimson_color), self, "Crimson Rift Color")
        if color.isValid():
            self._crimson_color = color.name()
            self._apply_color_btn(self.crimson_color_btn, self._crimson_color)

    def _pick_nightmare_color(self):
        color = QColorDialog.getColor(QColor(self._nightmare_color), self, "Brutal Nightmare Color")
        if color.isValid():
            self._nightmare_color = color.name()
            self._apply_color_btn(self.nightmare_color_btn, self._nightmare_color)

    def _on_raid_toggle(self):
        # Ensure at least one raid remains visible
        if not self.show_crimson_check.isChecked() and not self.show_nightmare_check.isChecked():
            sender = self.sender()
            if sender == self.show_crimson_check:
                self.show_nightmare_check.setChecked(True)
            else:
                self.show_crimson_check.setChecked(True)

    def _on_vol_changed(self, val):
        self.vol_value_lbl.setText(f"{val}%")

    def _on_hotkey_combo_changed(self, idx):
        key = self.hotkey_combo.currentData()
        if key:
            self.key_recorder.set_key(key)

    def _on_key_recorded(self, key):
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
        self.key_recorder.cancel_recording()
        self.cfg["sound_enabled"] = self.sound_check.isChecked()
        self.cfg["alert_minutes"] = self.timing_combo.currentData()
        self.cfg["sound_file"] = self.sound_combo.currentData()
        self.cfg["volume"] = self.vol_slider.value()
        self.cfg["hotkey"] = self.hotkey_combo.currentData()
        self.cfg["theme"] = self.theme_combo.currentData()
        self.cfg["font_scale"] = self.font_combo.currentData()
        self.cfg["crimson_color"] = self._crimson_color
        self.cfg["nightmare_color"] = self._nightmare_color
        self.cfg["show_crimson"] = self.show_crimson_check.isChecked()
        self.cfg["show_nightmare"] = self.show_nightmare_check.isChecked()
        save_config(self.cfg)
        self.settings_saved.emit(self.cfg)
        self.close()

    def closeEvent(self, e):
        self.key_recorder.cancel_recording()
        super().closeEvent(e)


# ---------------------------------------------------------
# 7. HIGH-CLARITY COMPACT RAID CARD (RESPONSIVE NO-OVERLAP)
# ---------------------------------------------------------
class HighClarityRaidCard(QFrame):
    def __init__(self, raid_type, title, accent_color, icon_pixmap_path=None, icon_symbol=None, parent=None):
        super().__init__(parent)
        self.raid_type = raid_type
        self.title_text = title
        self.accent_color = accent_color
        self.icon_pixmap_path = icon_pixmap_path
        self.icon_symbol = icon_symbol
        self.font_scale = 1.0
        self.current_theme = THEMES["Dark"]
        self.last_status = None
        self.init_ui()

    def set_accent_color(self, color):
        self.accent_color = color
        self.title_lbl.setStyleSheet(f"color: {self.accent_color}; border: none;")
        self._update_border()

    def apply_theme(self, theme_data):
        self.current_theme = theme_data
        self._update_border()
        if self.last_status:
            self.update_status(self.last_status)

    def _update_border(self):
        bg = self.current_theme.get("card_bg", "rgba(18, 22, 32, 0.85)")
        border = self.current_theme.get("card_border", "rgba(255, 255, 255, 0.08)")
        self.setStyleSheet(f"""
            QFrame#raidCard_{self.raid_type} {{
                background-color: {bg};
                border: 1px solid {border};
                border-left: 3px solid {self.accent_color};
                border-radius: 5px;
            }}
        """)

    def set_font_scale(self, scale):
        self.font_scale = scale
        # Update fonts and icons cleanly
        self.title_lbl.setFont(QFont("Segoe UI", int(9 * scale), QFont.Weight.Bold))
        self.status_badge.setFont(QFont("Segoe UI", max(7, int(7.5 * scale)), QFont.Weight.Bold))
        self.action_lbl.setFont(QFont("Segoe UI", max(7, int(8 * scale)), QFont.Weight.Bold))
        self.countdown_lbl.setFont(QFont("Consolas", int(12 * scale), QFont.Weight.Bold))
        self.local_time_lbl.setFont(QFont("Segoe UI", max(7, int(8 * scale)), QFont.Weight.Bold))

        if hasattr(self, "icon_lbl"):
            if self.icon_pixmap_path and os.path.exists(self.icon_pixmap_path):
                sz = int(16 * scale)
                pix = QPixmap(self.icon_pixmap_path).scaled(
                    sz, sz,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
                self.icon_lbl.setPixmap(pix)
            elif self.icon_symbol:
                self.icon_lbl.setFont(QFont("Segoe UI", int(10 * scale)))

        badge_w = int(82 * scale)
        badge_h = int(18 * scale)
        self.status_badge.setFixedSize(badge_w, badge_h)

    def init_ui(self):
        self.setObjectName(f"raidCard_{self.raid_type}")
        self._update_border()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(2)

        # Line 1: Icon + Title + Status Badge
        top_line = QHBoxLayout()
        top_line.setSpacing(6)

        if self.icon_pixmap_path and os.path.exists(self.icon_pixmap_path):
            self.icon_lbl = QLabel()
            pix = QPixmap(self.icon_pixmap_path).scaled(
                16, 16,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            self.icon_lbl.setPixmap(pix)
            top_line.addWidget(self.icon_lbl)
        elif self.icon_symbol:
            self.icon_lbl = QLabel(self.icon_symbol)
            self.icon_lbl.setFont(QFont("Segoe UI", 10))
            top_line.addWidget(self.icon_lbl)

        self.title_lbl = QLabel(self.title_text)
        self.title_lbl.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        self.title_lbl.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        self.title_lbl.setStyleSheet(f"color: {self.accent_color}; border: none;")
        top_line.addWidget(self.title_lbl)

        top_line.addStretch()

        self.status_badge = QLabel("NORMAL")
        self.status_badge.setFixedSize(82, 18)
        self.status_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_badge.setFont(QFont("Segoe UI", 7, QFont.Weight.Bold))
        top_line.addWidget(self.status_badge)
        layout.addLayout(top_line)

        # Line 2: Action Prefix + Countdown + Local Time
        bottom_line = QHBoxLayout()
        bottom_line.setSpacing(8)

        self.action_lbl = QLabel("STARTS IN:")
        self.action_lbl.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        self.action_lbl.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        self.action_lbl.setStyleSheet("color: #94A3B8; border: none;")
        bottom_line.addWidget(self.action_lbl)

        self.countdown_lbl = QLabel("00:00:00")
        self.countdown_lbl.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        self.countdown_lbl.setFont(QFont("Consolas", 12, QFont.Weight.Bold))
        self.countdown_lbl.setStyleSheet(f"color: {self.accent_color}; border: none;")
        bottom_line.addWidget(self.countdown_lbl)

        bottom_line.addStretch(1)

        self.local_time_lbl = QLabel("Normal --:-- • Hard --:--")
        self.local_time_lbl.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        self.local_time_lbl.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        self.local_time_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.local_time_lbl.setStyleSheet("color: #64748B; border: none;")
        bottom_line.addWidget(self.local_time_lbl)

        layout.addLayout(bottom_line)

    def update_status(self, status):
        self.last_status = status
        is_active = status["is_active"]
        seconds_left = status["seconds_left"]
        difficulty = status.get("difficulty", "Normal")
        theme = self.current_theme

        if is_active:
            if difficulty == "Normal":
                # Active Normal (Theme harmonized)
                self.status_badge.setText("● NORMAL")
                bg = theme.get("badge_act_norm_bg", "rgba(6, 78, 59, 0.95)")
                fg = theme.get("badge_act_norm_fg", "#00FF88")
                self.status_badge.setStyleSheet(
                    f"background-color: {bg}; color: {fg}; "
                    f"border: 1.5px solid {fg}; border-radius: 3px; font-weight: bold;"
                )
                self.action_lbl.setText("ENDS IN:")
                self.action_lbl.setStyleSheet(f"color: {fg}; font-weight: bold; border: none;")
                self.countdown_lbl.setText(format_countdown(seconds_left))
                self.countdown_lbl.setStyleSheet(f"color: {fg}; font-weight: bold; border: none;")

                w = status.get("active_window")
                next_w = status.get("next_window")
                if next_w:
                    self.local_time_lbl.setText(f"Hard starts {format_local_time(next_w['start_ts'])}")
                elif w:
                    self.local_time_lbl.setText(f"Ends {format_local_time(w['end_ts'])}")
                self.local_time_lbl.setStyleSheet(f"color: {fg}; font-weight: bold; border: none;")
            else:
                # Active Hard (Theme harmonized)
                self.status_badge.setText("● HARD")
                bg = theme.get("badge_act_hard_bg", "rgba(127, 29, 29, 0.95)")
                fg = theme.get("badge_act_hard_fg", "#FF4D4D")
                self.status_badge.setStyleSheet(
                    f"background-color: {bg}; color: {fg}; "
                    f"border: 1.5px solid {fg}; border-radius: 3px; font-weight: bold;"
                )
                self.action_lbl.setText("ENDS IN:")
                self.action_lbl.setStyleSheet(f"color: {fg}; font-weight: bold; border: none;")
                self.countdown_lbl.setText(format_countdown(seconds_left))
                self.countdown_lbl.setStyleSheet(f"color: {fg}; font-weight: bold; border: none;")

                w = status.get("active_window")
                if w:
                    self.local_time_lbl.setText(f"Ends {format_local_time(w['end_ts'])}")
                self.local_time_lbl.setStyleSheet(f"color: {fg}; font-weight: bold; border: none;")
        else:
            # Upcoming state (Theme harmonized)
            if difficulty == "Normal":
                self.status_badge.setText("NORMAL")
                bg = theme.get("badge_norm_bg", "#0F2942")
                fg = theme.get("badge_norm_fg", "#38BDF8")
                border = theme.get("badge_norm_border", "#0284C7")
                self.status_badge.setStyleSheet(
                    f"background-color: {bg}; color: {fg}; "
                    f"border: 1px solid {border}; border-radius: 3px; font-weight: bold;"
                )
            else:
                self.status_badge.setText("HARD")
                bg = theme.get("badge_hard_bg", "#3B1219")
                fg = theme.get("badge_hard_fg", "#FB7185")
                border = theme.get("badge_hard_border", "#E11D48")
                self.status_badge.setStyleSheet(
                    f"background-color: {bg}; color: {fg}; "
                    f"border: 1px solid {border}; border-radius: 3px; font-weight: bold;"
                )

            self.action_lbl.setText("STARTS IN:")
            self.action_lbl.setStyleSheet(f"color: {theme.get('muted_color', '#94A3B8')}; font-weight: bold; border: none;")
            self.countdown_lbl.setText(format_countdown(seconds_left))
            self.countdown_lbl.setStyleSheet(f"color: {self.accent_color}; font-weight: bold; border: none;")

            # Display times with clean no-overlap formatting
            next_w = status.get("upcoming_window")
            following_w = status.get("following_window")
            if next_w and following_w:
                t_norm = format_local_time(next_w["start_ts"])
                t_hard = format_local_time(following_w["start_ts"])
                self.local_time_lbl.setText(f"Normal {t_norm} • Hard {t_hard}")
            elif next_w:
                t_next = format_local_time(next_w["start_ts"])
                self.local_time_lbl.setText(f"Starts {t_next}")
            self.local_time_lbl.setStyleSheet(f"color: {theme.get('footer_color', '#94A3B8')}; font-weight: bold; border: none;")


# ---------------------------------------------------------
# 8. MAIN OVERLAY WINDOW WITH DRAG RESIZING & CUSTOM SIZE
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
        self.font_scale = self.cfg.get("font_scale", 1.0)
        self.current_theme_name = self.cfg.get("theme", "Dark")
        self.saved_width = max(MIN_WINDOW_W, self.cfg.get("win_width", 365))
        self.saved_height = max(MIN_WINDOW_H, self.cfg.get("win_height", 144))

        # Resizing states
        self.resizing_edge = None
        self.resize_start_pos = None
        self.resize_start_geo = None

        self.init_ui()
        self.setMouseTracking(True)
        self.container.setMouseTracking(True)

        self.hotkey_monitor = HotkeyMonitor(self.current_hotkey, self)
        self.hotkey_monitor.triggered.connect(self.toggle_pin)

        # Apply saved appearance
        self._apply_theme(self.current_theme_name)
        self._apply_font_scale(self.font_scale)
        self._apply_custom_raid_colors()
        self._apply_raid_visibility(force_fit=False)
        self._update_hotkey_labels()
        self._sync_min_size()

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
        self.setMinimumSize(MIN_WINDOW_W, MIN_WINDOW_H)
        self.resize(self.saved_width, self.saved_height)

        # Window Icon
        icon_path = os.path.join(APP_DIR, "app_icon.ico")
        if not os.path.exists(icon_path):
            icon_path = os.path.join(RESOURCE_DIR, "app_icon.ico")
        if not os.path.exists(icon_path):
            icon_path = os.path.join(SOUNDS_DIR, "app_icon.png")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        # Restore saved position (clamped to available screens so it never gets lost off-screen)
        pos = self.cfg.get("overlay_pos", {"x": 80, "y": 80})
        px, py = pos.get("x", 80), pos.get("y", 80)
        on_screen = False
        for scr in QApplication.screens():
            if scr.availableGeometry().contains(px + 20, py + 20):
                on_screen = True
                break
        if not on_screen:
            px, py = 80, 80
        self.move(px, py)

        # Main Card Frame
        self.container = QFrame(self)
        self.container.setGeometry(0, 0, self.saved_width, self.saved_height)
        self.container.setObjectName("mainFrame")
        self._apply_frame_style(False)

        self.main_layout = QVBoxLayout(self.container)
        self.main_layout.setContentsMargins(8, 6, 8, 6)
        self.main_layout.setSpacing(4)

        # 1. Top Header Row (hidden in minimal pass-through mode)
        self.header_widget = QWidget()
        header = QHBoxLayout(self.header_widget)
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(4)

        self.title_lbl = QLabel("⚔️ CHRONICLES RAID TIMER")
        self.title_lbl.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        header.addWidget(self.title_lbl)

        header.addStretch()

        # Settings Button ⚙️
        self.settings_btn = QPushButton("⚙️")
        self.settings_btn.setFixedSize(22, 18)
        self.settings_btn.setStyleSheet("""
            QPushButton { background: rgba(255,255,255,0.08); color: #AAA; border: 1px solid rgba(255,255,255,0.15); border-radius: 3px; font-size: 10px; }
            QPushButton:hover { background: #00ADB5; color: #FFF; }
        """)
        self.settings_btn.setToolTip("Settings")
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
        self.close_btn = QPushButton("✕")
        self.close_btn.setFixedSize(16, 18)
        self.close_btn.setStyleSheet("""
            QPushButton { background: transparent; color: #777; border: none; font-weight: bold; font-size: 11px; }
            QPushButton:hover { color: #FF4C4C; }
        """)
        self.close_btn.setToolTip("Close Overlay")
        self.close_btn.clicked.connect(self.close_app)
        header.addWidget(self.close_btn)

        self.main_layout.addWidget(self.header_widget)

        # 2. Crimson Rift Card
        crimson_color = self.cfg.get("crimson_color", "#FF3366")
        self.crimson_card = HighClarityRaidCard(
            raid_type="crimson",
            title="Crimson Rift",
            accent_color=crimson_color,
            icon_pixmap_path=CRIMSON_ICON_PATH,
            parent=self.container
        )
        self.main_layout.addWidget(self.crimson_card)

        # 3. Brutal Nightmare Card
        nightmare_color = self.cfg.get("nightmare_color", "#A855F7")
        self.nightmare_card = HighClarityRaidCard(
            raid_type="nightmare",
            title="Brutal Nightmare",
            accent_color=nightmare_color,
            icon_symbol="💀",
            parent=self.container
        )
        self.main_layout.addWidget(self.nightmare_card)

        # 4. Footer Row (Dynamic Lock Mode + Sound Alert Badge + Prominent Creator Credit)
        self.footer_widget = QWidget()
        footer = QHBoxLayout(self.footer_widget)
        footer.setContentsMargins(0, 0, 0, 0)
        footer.setSpacing(6)

        # Enhanced Lock Status Badge (Clearer, larger, high clarity)
        self.status_badge = QLabel(f"🔓 {self.current_hotkey}: Lock")
        self.status_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        footer.addWidget(self.status_badge)

        footer.addStretch()

        self.alert_badge = QLabel("🔔 5m")
        self.alert_badge.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        self._update_alert_badge()
        footer.addWidget(self.alert_badge)

        footer.addSpacing(6)

        # Creator Credit
        self.creator_lbl = QLabel("Created by NoYz")
        self.creator_lbl.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        footer.addWidget(self.creator_lbl)

        # Size grip corner for smooth resizing
        self.size_grip = QSizeGrip(self)
        self.size_grip.setFixedSize(14, 14)
        footer.addWidget(self.size_grip)

        self.main_layout.addWidget(self.footer_widget)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        w = self.width()
        h = self.height()
        self.container.setGeometry(0, 0, w, h)
        if not self.is_pinned:
            self.saved_width = w
            self.saved_height = h
            self.cfg["win_width"] = w
            self.cfg["win_height"] = h

    def _apply_theme(self, theme_name):
        self.current_theme_name = theme_name
        theme = THEMES.get(theme_name, THEMES["Dark"])

        self._apply_frame_style(self.is_pinned)
        self.title_lbl.setStyleSheet(f"color: {theme['title_color']}; border: none;")
        self.creator_lbl.setStyleSheet(f"color: {theme['creator_color']}; border: none;")

        self.crimson_card.apply_theme(theme)
        self.nightmare_card.apply_theme(theme)
        self._apply_pin_btn_style(self.is_pinned)
        self._update_hotkey_labels()
        self._update_alert_badge()

    def _sync_min_size(self, force_fit=False):
        """Ensure window never shrinks below the layout's true non-overlapping minimum size."""
        self.main_layout.activate()
        min_sz = self.main_layout.minimumSize()
        card_w = 0
        if self.crimson_card.isVisible():
            self.crimson_card.layout().activate()
            card_w = max(card_w, self.crimson_card.minimumSizeHint().width())
        if self.nightmare_card.isVisible():
            self.nightmare_card.layout().activate()
            card_w = max(card_w, self.nightmare_card.minimumSizeHint().width())
        footer_w = self.footer_widget.minimumSizeHint().width() if self.footer_widget.isVisible() else 0
        header_w = self.header_widget.minimumSizeHint().width() if self.header_widget.isVisible() else 0

        min_w = max(min_sz.width(), card_w + 20, footer_w + 20, header_w + 20)
        min_h = max(48, min_sz.height() + 4)

        if min_w != self.minimumWidth() or min_h != self.minimumHeight():
            self.setMinimumSize(min_w, min_h)

        if force_fit:
            target_w = max(self.saved_width, min_w)
            if target_w != self.width() or min_h != self.height():
                self.resize(target_w, min_h)
        else:
            new_w = max(self.width(), min_w)
            new_h = max(self.height(), min_h)
            if new_w != self.width() or new_h != self.height():
                self.resize(new_w, new_h)

    def _apply_raid_visibility(self, force_fit=True):
        show_cr = self.cfg.get("show_crimson", True)
        show_nm = self.cfg.get("show_nightmare", True)
        if not show_cr and not show_nm:
            show_cr = True
        self.crimson_card.setVisible(show_cr)
        self.nightmare_card.setVisible(show_nm)
        self._sync_min_size(force_fit=force_fit)

    def _apply_font_scale(self, scale):
        self.font_scale = scale
        self.title_lbl.setFont(QFont("Segoe UI", max(7, int(8 * scale)), QFont.Weight.Bold))
        self.creator_lbl.setFont(QFont("Segoe UI", max(7, int(8 * scale)), QFont.Weight.Bold))
        self.crimson_card.set_font_scale(scale)
        self.nightmare_card.set_font_scale(scale)
        self._update_hotkey_labels()
        self._update_alert_badge()
        self._sync_min_size()

    def _apply_custom_raid_colors(self):
        cr_color = self.cfg.get("crimson_color", "#FF3366")
        nm_color = self.cfg.get("nightmare_color", "#A855F7")
        self.crimson_card.set_accent_color(cr_color)
        self.nightmare_card.set_accent_color(nm_color)

    def apply_hotkey(self, new_key):
        if not new_key:
            return
        self.current_hotkey = new_key
        if hasattr(self, 'hotkey_monitor') and self.hotkey_monitor:
            self.hotkey_monitor.set_key(new_key)
        self._update_hotkey_labels()

    def _update_hotkey_labels(self):
        f_size = max(7, int(8 * self.font_scale))
        theme = THEMES.get(self.current_theme_name, THEMES["Dark"])
        accent = theme.get("accent", "#00ADB5")

        if self.is_pinned:
            self.status_badge.setText(f"🔒 LOCKED [{self.current_hotkey}]")
            self.status_badge.setFont(QFont("Segoe UI", f_size, QFont.Weight.Bold))
            self.status_badge.setStyleSheet(f"""
                QLabel {{
                    background: rgba(255, 255, 255, 0.12);
                    color: {accent};
                    border: 1px solid {accent};
                    border-radius: 4px;
                    padding: 2px 6px;
                    font-weight: bold;
                }}
            """)
        else:
            self.status_badge.setText(f"🔓 {self.current_hotkey}: Lock")
            self.status_badge.setFont(QFont("Segoe UI", f_size, QFont.Weight.Bold))
            self.status_badge.setStyleSheet(f"""
                QLabel {{
                    background: rgba(255, 255, 255, 0.08);
                    color: {theme.get('text_color', '#DDD')};
                    border: 1px solid rgba(255, 255, 255, 0.18);
                    border-radius: 4px;
                    padding: 2px 6px;
                    font-weight: bold;
                }}
            """)
        self.pin_btn.setToolTip(f"Toggle Pass-Through Lock [{self.current_hotkey}]")

    def _update_alert_badge(self):
        theme = THEMES.get(self.current_theme_name, THEMES["Dark"])
        f_size = max(7, int(8 * self.font_scale))
        self.alert_badge.setFont(QFont("Segoe UI", f_size, QFont.Weight.Bold))

        if self.cfg.get("sound_enabled", True):
            m = self.cfg.get("alert_minutes", 5)
            vol = self.cfg.get("volume", 50)
            txt = f"🔔 Start ({vol}%)" if m == 0 else f"🔔 {m}m ({vol}%)"
            self.alert_badge.setText(txt)
            self.alert_badge.setStyleSheet(f"color: {theme.get('accent', '#00E5FF')}; border: none;")
        else:
            self.alert_badge.setText("🔕 Muted")
            self.alert_badge.setStyleSheet("color: #64748B; border: none;")

    def _apply_frame_style(self, locked):
        theme = THEMES.get(self.current_theme_name, THEMES["Dark"])
        bg = theme["frame_bg_locked"] if locked else theme["frame_bg"]
        border = theme["frame_border_locked"] if locked else theme["frame_border"]
        self.container.setStyleSheet(f"""
            QFrame#mainFrame {{
                background-color: {bg};
                border: {border};
                border-radius: 7px;
            }}
        """)

    def _apply_pin_btn_style(self, locked):
        theme = THEMES.get(self.current_theme_name, THEMES["Dark"])
        accent = theme.get("accent", "#00ADB5")
        title_c = theme.get("title_color", "#FFD700")
        if locked:
            self.pin_btn.setText("🔒")
            self.pin_btn.setStyleSheet(f"""
                QPushButton {{ background: {accent}; color: #000; border: 1px solid {accent}; border-radius: 3px; font-size: 10px; font-weight: bold; }}
                QPushButton:hover {{ background: #FFF; color: #000; }}
            """)
        else:
            self.pin_btn.setText("📌")
            self.pin_btn.setStyleSheet(f"""
                QPushButton {{ background: rgba(255, 255, 255, 0.08); color: {title_c}; border: 1px solid rgba(255, 255, 255, 0.22); border-radius: 3px; font-size: 10px; font-weight: bold; }}
                QPushButton:hover {{ background: {title_c}; color: #000; }}
            """)

    def toggle_pin(self):
        # Ignore hotkey trigger while Settings dialog is open (prevents accidental lock when recording hotkey)
        if self.settings_dlg is not None and self.settings_dlg.isVisible():
            return
        self.is_pinned = not self.is_pinned
        hwnd = int(self.winId())
        current_style = user32.GetWindowLongPtrW(ctypes.c_void_p(hwnd), GWL_EXSTYLE)

        if self.is_pinned:
            # ACTIVATE pass-through + minimal mode
            user32.SetWindowLongPtrW(
                ctypes.c_void_p(hwnd),
                GWL_EXSTYLE,
                ctypes.c_longlong(current_style | WS_EX_TRANSPARENT | WS_EX_LAYERED)
            )
            self._apply_frame_style(True)
            self._apply_pin_btn_style(True)
            self._update_hotkey_labels()

            # Hide header and footer for minimal mode
            self.header_widget.setVisible(False)
            self.footer_widget.setVisible(False)

            # Shrink height only to fit visible cards, KEEP custom width
            self._sync_min_size(force_fit=True)

        else:
            # DEACTIVATE pass-through
            user32.SetWindowLongPtrW(
                ctypes.c_void_p(hwnd),
                GWL_EXSTYLE,
                ctypes.c_longlong(current_style & ~WS_EX_TRANSPARENT)
            )
            self._apply_frame_style(False)
            self._apply_pin_btn_style(False)
            self._update_hotkey_labels()

            # Show header and footer
            self.header_widget.setVisible(True)
            self.footer_widget.setVisible(True)

            # Restore full custom size (never smaller than minimum)
            self._sync_min_size(force_fit=False)
            self.resize(max(self.saved_width, self.minimumWidth()), max(self.saved_height, self.minimumHeight()))

    # ---------------------------------------------------------
    # INTERACTIVE BORDER DRAG-TO-RESIZE
    # ---------------------------------------------------------
    def _detect_resize_edge(self, pos):
        if self.is_pinned:
            return None
        r = self.rect()
        near_right = abs(pos.x() - r.width()) <= RESIZE_MARGIN
        near_bottom = abs(pos.y() - r.height()) <= RESIZE_MARGIN
        near_left = pos.x() <= RESIZE_MARGIN
        near_top = pos.y() <= RESIZE_MARGIN

        if near_right and near_bottom:
            return "bottom_right"
        if near_right:
            return "right"
        if near_bottom:
            return "bottom"
        return None

    def mousePressEvent(self, e):
        if self.is_pinned:
            return
        if e.button() == Qt.MouseButton.LeftButton:
            edge = self._detect_resize_edge(e.pos())
            if edge:
                self.resizing_edge = edge
                self.resize_start_pos = e.globalPosition().toPoint()
                self.resize_start_geo = self.geometry()
            else:
                self.resizing_edge = None
                self.drag_position = e.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, e):
        if self.is_pinned:
            return

        if self.resizing_edge and (e.buttons() & Qt.MouseButton.LeftButton):
            delta = e.globalPosition().toPoint() - self.resize_start_pos
            orig = self.resize_start_geo
            new_w = orig.width()
            new_h = orig.height()

            if "right" in self.resizing_edge:
                new_w = max(self.minimumWidth(), orig.width() + delta.x())
            if "bottom" in self.resizing_edge:
                new_h = max(self.minimumHeight(), orig.height() + delta.y())

            self.resize(new_w, new_h)
            return

        # Update cursor on hover near borders
        edge = self._detect_resize_edge(e.pos())
        if edge == "bottom_right":
            self.setCursor(Qt.CursorShape.SizeFDiagCursor)
        elif edge == "right":
            self.setCursor(Qt.CursorShape.SizeHorCursor)
        elif edge == "bottom":
            self.setCursor(Qt.CursorShape.SizeVerCursor)
        else:
            self.setCursor(Qt.CursorShape.ArrowCursor)

        if e.buttons() == Qt.MouseButton.LeftButton and not self.resizing_edge:
            self.move(e.globalPosition().toPoint() - self.drag_position)

    def mouseReleaseEvent(self, e):
        if not self.is_pinned:
            self.resizing_edge = None
            self.setCursor(Qt.CursorShape.ArrowCursor)
            self.cfg["overlay_pos"] = {"x": self.x(), "y": self.y()}
            self.cfg["win_width"] = self.width()
            self.cfg["win_height"] = self.height()
            save_config(self.cfg)

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

        new_theme = self.cfg.get("theme", "Dark")
        if new_theme != self.current_theme_name:
            self._apply_theme(new_theme)

        new_fscale = self.cfg.get("font_scale", 1.0)
        if abs(new_fscale - self.font_scale) > 0.02:
            self._apply_font_scale(new_fscale)

        self._apply_custom_raid_colors()
        self._apply_raid_visibility(force_fit=True)
        self._update_alert_badge()
        self._update_hotkey_labels()

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
            if 0 <= sec_left <= alert_offset_sec and (alert_offset_sec - sec_left) <= 15:
                key = (raid_name, start_ts, alert_offset_sec)
                if key not in self.triggered_alerts:
                    self.triggered_alerts.add(key)
                    SoundManager.play(sound_file, volume)

        # Also handle "At Raid Start" (alert_minutes == 0) right after raid becomes active
        if alert_minutes == 0:
            act_win = status.get("active_window")
            if act_win:
                start_ts = act_win["start_ts"]
                elapsed = now - start_ts
                if 0 <= elapsed <= 5:
                    key = (raid_name, start_ts, 0)
                    if key not in self.triggered_alerts:
                        self.triggered_alerts.add(key)
                        SoundManager.play(sound_file, volume)

    def update_all_raids(self):
        now = time.time()
        if self.cfg.get("show_crimson", True):
            crimson_status = get_raid_status("crimson", now)
            self.crimson_card.update_status(crimson_status)
            self.check_audio_alert("crimson", crimson_status, now)

        if self.cfg.get("show_nightmare", True):
            nightmare_status = get_raid_status("nightmare", now)
            self.nightmare_card.update_status(nightmare_status)
            self.check_audio_alert("nightmare", nightmare_status, now)

        self._sync_min_size()

        if len(self.triggered_alerts) > 20:
            self.triggered_alerts = {k for k in self.triggered_alerts if now - k[1] < 86400}

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
        self.cfg["win_width"] = self.width()
        self.cfg["win_height"] = self.height()
        save_config(self.cfg)
        self.close()
        QApplication.quit()


# ---------------------------------------------------------
# 9. UNINSTALLER WIZARD (BUILT-IN FOR ULTRA-COMPACT SIZE)
# ---------------------------------------------------------
class UninstallerWizard(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("⚔️ ArcheAge Chronicles Raid Timer - Uninstaller")
        self.setFixedSize(440, 260)
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.WindowCloseButtonHint)
        self.setStyleSheet("""
            QWidget {
                background-color: #0E121A;
                color: #FFFFFF;
                font-family: 'Segoe UI';
            }
            QFrame#card {
                background-color: #141924;
                border: 1px solid #252F42;
                border-radius: 8px;
            }
            QPushButton {
                border-radius: 4px;
                font-weight: bold;
                padding: 6px 14px;
                font-size: 11px;
            }
            QCheckBox {
                color: #CBD5E1;
                font-size: 11px;
                spacing: 6px;
            }
            QProgressBar {
                background-color: #1A2230;
                border: 1px solid #2B384E;
                border-radius: 4px;
                text-align: center;
                color: #FFF;
                font-size: 10px;
                font-weight: bold;
                height: 16px;
            }
            QProgressBar::chunk {
                background-color: #E63946;
                border-radius: 3px;
            }
        """)

        if getattr(sys, 'frozen', False):
            self.install_dir = os.path.dirname(sys.executable)
        else:
            self.install_dir = os.path.dirname(os.path.abspath(__file__))

        self.desktop_lnk = os.path.join(os.path.expanduser("~"), "Desktop", "ArcheAge Raid Timer.lnk")
        self.start_menu_dir = os.path.join(
            os.environ.get("APPDATA", ""), 
            "Microsoft", "Windows", "Start Menu", "Programs", "ArcheAge Raid Timer"
        )

        icon_path = os.path.join(self.install_dir, "app_icon.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 14, 16, 14)
        main_layout.setSpacing(10)

        card = QFrame()
        card.setObjectName("card")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(14, 12, 14, 12)
        card_layout.setSpacing(8)

        title_lbl = QLabel("⚔️ Uninstall ArcheAge Chronicles Raid Timer")
        title_lbl.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        title_lbl.setStyleSheet("color: #E63946; border: none;")
        card_layout.addWidget(title_lbl)

        self.desc_lbl = QLabel(
            "Are you sure you want to completely remove ArcheAge Chronicles Raid Timer "
            "and all its shortcuts from your computer?"
        )
        self.desc_lbl.setWordWrap(True)
        self.desc_lbl.setStyleSheet("color: #94A3B8; font-size: 11px; border: none;")
        card_layout.addWidget(self.desc_lbl)

        loc_lbl = QLabel(f"Location: {self.install_dir}")
        loc_lbl.setStyleSheet("color: #64748B; font-size: 9px; font-family: Consolas; border: none;")
        loc_lbl.setWordWrap(True)
        card_layout.addWidget(loc_lbl)

        self.remove_data_check = QCheckBox("Also remove custom sounds and configuration (config.json)")
        self.remove_data_check.setChecked(True)
        card_layout.addWidget(self.remove_data_check)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(False)
        card_layout.addWidget(self.progress_bar)

        self.status_lbl = QLabel("")
        self.status_lbl.setStyleSheet("color: #00ADB5; font-size: 10px; font-weight: bold; border: none;")
        self.status_lbl.setVisible(False)
        card_layout.addWidget(self.status_lbl)

        main_layout.addWidget(card)

        btn_layout = QHBoxLayout()
        creator_lbl = QLabel("Created by NoYz")
        creator_lbl.setStyleSheet("color: #00ADB5; font-size: 9px; font-weight: bold;")
        btn_layout.addWidget(creator_lbl)

        btn_layout.addStretch()

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setStyleSheet("background: #252F42; color: #FFF; border: 1px solid #3B4B66;")
        self.cancel_btn.clicked.connect(self.close)
        btn_layout.addWidget(self.cancel_btn)

        self.uninstall_btn = QPushButton("Uninstall Now")
        self.uninstall_btn.setStyleSheet("background: #E63946; color: #FFF; border: none;")
        self.uninstall_btn.clicked.connect(self.start_uninstallation)
        btn_layout.addWidget(self.uninstall_btn)

        main_layout.addLayout(btn_layout)

    def start_uninstallation(self):
        self.uninstall_btn.setEnabled(False)
        self.cancel_btn.setEnabled(False)
        self.remove_data_check.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.status_lbl.setVisible(True)

        self.progress_bar.setValue(20)
        self.status_lbl.setText("Removing Desktop shortcuts...")
        QTimer.singleShot(300, self._step2)

    def _step2(self):
        if os.path.exists(self.desktop_lnk):
            try: os.remove(self.desktop_lnk)
            except Exception: pass

        self.progress_bar.setValue(50)
        self.status_lbl.setText("Removing Start Menu shortcuts...")
        QTimer.singleShot(300, self._step3)

    def _step3(self):
        if os.path.exists(self.start_menu_dir):
            try: shutil.rmtree(self.start_menu_dir, ignore_errors=True)
            except Exception: pass

        self.progress_bar.setValue(80)
        self.status_lbl.setText("Cleaning program files...")
        QTimer.singleShot(300, self._step4)

    def _step4(self):
        remove_all = self.remove_data_check.isChecked()
        try:
            for item in os.listdir(self.install_dir):
                item_path = os.path.join(self.install_dir, item)
                if getattr(sys, 'frozen', False):
                    if item.lower() in [os.path.basename(sys.executable).lower(), "uninstall.exe"]:
                        continue
                if not remove_all and (item == "config.json" or item == "sounds"):
                    continue
                try:
                    if os.path.isdir(item_path):
                        shutil.rmtree(item_path, ignore_errors=True)
                    else:
                        os.remove(item_path)
                except Exception:
                    pass
        except Exception:
            pass

        self.progress_bar.setValue(100)
        self.status_lbl.setText("Uninstallation completed successfully!")
        self.status_lbl.setStyleSheet("color: #00FF88; font-size: 11px; font-weight: bold; border: none;")

        self.desc_lbl.setText("ArcheAge Chronicles Raid Timer has been successfully uninstalled from your computer.")
        self.uninstall_btn.setVisible(False)
        self.cancel_btn.setText("Close")
        self.cancel_btn.setEnabled(True)
        self.cancel_btn.setStyleSheet("background: #00ADB5; color: #000; border: none;")
        self.cancel_btn.clicked.connect(self._finish_and_cleanup)

    def _finish_and_cleanup(self):
        cmd = f'cmd.exe /c timeout /t 2 /nobreak >nul & rmdir /s /q "{self.install_dir}"'
        try:
            import subprocess
            subprocess.Popen(cmd, shell=True, creationflags=0x08000000)
        except Exception:
            pass
        self.close()


# ---------------------------------------------------------
# 10. ENTRY POINT
# ---------------------------------------------------------
if __name__ == "__main__":
    if "--uninstall" in sys.argv:
        app = QApplication(sys.argv)
        app.setQuitOnLastWindowClosed(False)
        wizard = UninstallerWizard()
        wizard.show()
        sys.exit(app.exec())
    else:
        # Single-instance guard using native Windows Mutex (prevents duplicate overlays)
        _mutex = None
        try:
            _mutex = ctypes.windll.kernel32.CreateMutexW(None, False, "ArcheAge_Chronicles_Raid_Timer_Mutex")
            if ctypes.windll.kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
                sys.exit(0)
        except Exception:
            pass

        app = QApplication(sys.argv)
        app.setQuitOnLastWindowClosed(False)
        overlay = RaidTimerOverlay()
        overlay.show()
        sys.exit(app.exec())
