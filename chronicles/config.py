"""Configuration persistence, validation, and import/export."""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass, field, asdict
from typing import Any

from chronicles.models import RaidDefinition, default_builtin_raids


def get_app_root() -> str:
    """Return the root folder containing the application code/executable."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get_resource_root() -> str:
    """Return the read-only bundled resource root (supports PyInstaller _MEIPASS)."""
    if getattr(sys, "frozen", False):
        return getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    return get_app_root()


def _is_dir_writable(path: str) -> bool:
    try:
        os.makedirs(path, exist_ok=True)
        probe = os.path.join(path, ".write_test")
        with open(probe, "w", encoding="utf-8") as fh:
            fh.write("ok")
        os.remove(probe)
        return True
    except OSError:
        return False


def get_data_dir() -> str:
    """Return writable user configuration/assets directory."""
    env_dir = os.environ.get("CHRONICLES_DATA_DIR")
    if env_dir and _is_dir_writable(env_dir):
        return env_dir

    app_root = get_app_root()
    portable_flag = os.path.join(app_root, "portable.flag")
    local_cfg = os.path.join(app_root, "config.json")
    local_data = os.path.join(app_root, "data")

    if os.path.exists(portable_flag) or os.path.exists(local_cfg):
        return app_root

    if not getattr(sys, "frozen", False) and _is_dir_writable(local_data):
        return local_data

    local_appdata = os.environ.get(
        "LOCALAPPDATA", os.path.join(os.path.expanduser("~"), "AppData", "Local")
    )
    appdata_dir = os.path.join(local_appdata, "ChroniclesRaidTimer")
    if _is_dir_writable(appdata_dir):
        return appdata_dir

    if _is_dir_writable(local_data):
        return local_data

    import tempfile

    fallback = os.path.join(tempfile.gettempdir(), "ChroniclesRaidTimer")
    os.makedirs(fallback, exist_ok=True)
    return fallback


def get_config_path() -> str:
    return os.path.join(get_data_dir(), "config.json")


def get_custom_sounds_dir() -> str:
    path = os.path.join(get_data_dir(), "custom_sounds")
    os.makedirs(path, exist_ok=True)
    return path


def get_builtin_sounds_dir() -> str:
    res_sounds = os.path.join(get_resource_root(), "assets", "sounds")
    if os.path.exists(res_sounds):
        return res_sounds
    app_sounds = os.path.join(get_app_root(), "assets", "sounds")
    os.makedirs(app_sounds, exist_ok=True)
    return app_sounds


@dataclass
class AppConfig:
    """Complete application configuration persisted as JSON."""

    # Window placement & mode
    overlay_x: int = 80
    overlay_y: int = 80
    hud_width: int = 410
    hud_height: int = 230
    hud_mode: str = "cards"  # "cards" | "compact" | "horizontal"

    # Visual appearance
    theme: str = "Obsidian Gold"
    unlocked_opacity: float = 0.94
    locked_opacity: float = 0.80
    font_scale: float = 1.0
    show_progress_rings: bool = True
    show_clock: bool = True
    clock_24h: bool = False
    snap_to_edges: bool = True
    sort_by_soonest: bool = True
    minimal_hide_chrome_on_lock: bool = True

    # Audio & Alerts
    sound_enabled: bool = True
    sound_file: str = "chronicles_horn.wav"
    volume: int = 60
    alert_milestones: list[int] = field(default_factory=lambda: [5, 0])
    alert_on_hard_transition: bool = True
    toast_enabled: bool = True
    toast_position: str = "bottom_right"
    tts_enabled: bool = False
    tts_volume: int = 75
    tts_voice: str = "preset:commander_david"
    tts_rate: float = -0.04
    tts_pitch: float = -0.14
    tts_style: str = "standard"

    # Hotkeys & System
    hotkey_lock: str = "F8"
    hotkey_toggle_hud: str = "F9"
    hotkey_compact: str = "F10"
    hotkey_snooze: str = ""
    minimize_to_tray: bool = True
    start_with_windows: bool = False

    # Tracked raids
    raids: list[RaidDefinition] = field(default_factory=default_builtin_raids)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["raids"] = [r.to_dict() for r in self.raids]
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AppConfig":
        defaults = cls()
        hud_mode = data.get("hud_mode", defaults.hud_mode)
        if hud_mode not in ("cards", "compact", "horizontal"):
            hud_mode = "cards"

        toast_pos = data.get("toast_position", defaults.toast_position)
        if toast_pos not in ("top_right", "top_left", "bottom_right", "bottom_left"):
            toast_pos = "bottom_right"

        raw_milestones = data.get("alert_milestones", defaults.alert_milestones)
        milestones: list[int] = []
        if isinstance(raw_milestones, list):
            for m in raw_milestones:
                try:
                    mi = int(m)
                    if 0 <= mi <= 60 and mi not in milestones:
                        milestones.append(mi)
                except (TypeError, ValueError):
                    pass
        if not milestones:
            milestones = [5, 0]
        milestones.sort(reverse=True)

        raw_raids = data.get("raids")
        raids: list[RaidDefinition] = []
        if isinstance(raw_raids, list) and raw_raids:
            seen_ids: set[str] = set()
            for idx, item in enumerate(raw_raids):
                if isinstance(item, dict):
                    rd = RaidDefinition.from_dict(item)
                    if rd.id not in seen_ids:
                        rd.order = idx
                        raids.append(rd)
                        seen_ids.add(rd.id)
        if not raids:
            raids = default_builtin_raids()

        return cls(
            overlay_x=int(data.get("overlay_x", defaults.overlay_x)),
            overlay_y=int(data.get("overlay_y", defaults.overlay_y)),
            hud_width=max(220, int(data.get("hud_width", defaults.hud_width))),
            hud_height=max(80, int(data.get("hud_height", defaults.hud_height))),
            hud_mode=hud_mode,
            theme=str(data.get("theme", defaults.theme)),
            unlocked_opacity=max(0.45, min(1.0, float(data.get("unlocked_opacity", defaults.unlocked_opacity)))),
            locked_opacity=max(0.25, min(1.0, float(data.get("locked_opacity", defaults.locked_opacity)))),
            font_scale=max(0.75, min(1.40, float(data.get("font_scale", defaults.font_scale)))),
            show_progress_rings=bool(data.get("show_progress_rings", defaults.show_progress_rings)),
            show_clock=bool(data.get("show_clock", defaults.show_clock)),
            clock_24h=bool(data.get("clock_24h", defaults.clock_24h)),
            snap_to_edges=bool(data.get("snap_to_edges", defaults.snap_to_edges)),
            sort_by_soonest=bool(data.get("sort_by_soonest", defaults.sort_by_soonest)),
            minimal_hide_chrome_on_lock=bool(
                data.get("minimal_hide_chrome_on_lock", defaults.minimal_hide_chrome_on_lock)
            ),
            sound_enabled=bool(data.get("sound_enabled", defaults.sound_enabled)),
            sound_file=str(data.get("sound_file", defaults.sound_file)),
            volume=max(0, min(100, int(data.get("volume", defaults.volume)))),
            alert_milestones=milestones,
            alert_on_hard_transition=bool(
                data.get("alert_on_hard_transition", defaults.alert_on_hard_transition)
            ),
            toast_enabled=bool(data.get("toast_enabled", defaults.toast_enabled)),
            toast_position=toast_pos,
            tts_enabled=bool(data.get("tts_enabled", defaults.tts_enabled)),
            tts_volume=max(0, min(100, int(data.get("tts_volume", defaults.tts_volume)))),
            tts_voice=str(data.get("tts_voice", defaults.tts_voice)),
            tts_rate=max(-1.0, min(1.0, float(data.get("tts_rate", defaults.tts_rate)))),
            tts_pitch=max(-1.0, min(1.0, float(data.get("tts_pitch", defaults.tts_pitch)))),
            tts_style=(
                str(data.get("tts_style", defaults.tts_style))
                if str(data.get("tts_style", defaults.tts_style)) in ("standard", "tactical", "epic")
                else "standard"
            ),
            hotkey_lock=str(data.get("hotkey_lock", defaults.hotkey_lock)),
            hotkey_toggle_hud=str(data.get("hotkey_toggle_hud", defaults.hotkey_toggle_hud)),
            hotkey_compact=str(data.get("hotkey_compact", defaults.hotkey_compact)),
            hotkey_snooze=str(data.get("hotkey_snooze", defaults.hotkey_snooze)),
            minimize_to_tray=bool(data.get("minimize_to_tray", defaults.minimize_to_tray)),
            start_with_windows=bool(data.get("start_with_windows", defaults.start_with_windows)),
            raids=raids,
        )


def load_config(path: str | None = None) -> AppConfig:
    """Load configuration from disk, returning defaults if missing or invalid."""
    cfg_path = path or get_config_path()
    if os.path.exists(cfg_path):
        try:
            with open(cfg_path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            if isinstance(data, dict):
                return AppConfig.from_dict(data)
        except Exception:
            pass
    return AppConfig()


def save_config(cfg: AppConfig, path: str | None = None) -> bool:
    """Persist configuration safely using atomic temp-file replacement."""
    cfg_path = path or get_config_path()
    parent = os.path.dirname(cfg_path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    tmp_path = cfg_path + ".tmp"
    try:
        with open(tmp_path, "w", encoding="utf-8") as fh:
            json.dump(cfg.to_dict(), fh, indent=2)
        os.replace(tmp_path, cfg_path)
        return True
    except Exception:
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except Exception:
            pass
        return False
