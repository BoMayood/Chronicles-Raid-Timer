"""Hook-free multi-action global hotkey polling via GetAsyncKeyState."""

from __future__ import annotations

import ctypes
import sys
from typing import Optional

from PyQt6.QtCore import QObject, QTimer, pyqtSignal

VK_MAP: dict[str, int] = {
    "F1": 0x70, "F2": 0x71, "F3": 0x72, "F4": 0x73,
    "F5": 0x74, "F6": 0x75, "F7": 0x76, "F8": 0x77,
    "F9": 0x78, "F10": 0x79, "F11": 0x7A, "F12": 0x7B,
    "INSERT": 0x2D, "DELETE": 0x2E, "HOME": 0x24, "END": 0x23,
    "PAGE UP": 0x21, "PAGE DOWN": 0x22, "PAUSE": 0x13,
    "SCROLL LOCK": 0x91, "PRINT SCREEN": 0x2C, "NUM LOCK": 0x90,
    "SPACE": 0x20, "TAB": 0x09, "ENTER": 0x0D, "RETURN": 0x0D,
    "BACKSPACE": 0x08, "ESCAPE": 0x1B,
}
for _digit in range(10):
    VK_MAP[str(_digit)] = 0x30 + _digit
for _char_ord in range(ord("A"), ord("Z") + 1):
    VK_MAP[chr(_char_ord)] = _char_ord

MODIFIER_VKS = {
    "CTRL": 0x11,
    "CONTROL": 0x11,
    "ALT": 0x12,
    "SHIFT": 0x10,
}

HOTKEY_PRESETS: list[str] = [
    "",
    "F8", "F9", "F10", "F11", "F12",
    "F1", "F2", "F3", "F4", "F5", "F6", "F7",
    "Ctrl+F8", "Ctrl+F9", "Ctrl+F10",
    "Alt+F8", "Alt+F9",
    "Insert", "Home", "End", "Page Up", "Page Down", "Pause", "Scroll Lock",
]


def parse_hotkey_binding(combo_str: str) -> Optional[tuple[tuple[int, ...], int]]:
    """Parse 'Ctrl+F8' or 'F8' into ((modifier_vks...), primary_vk)."""
    if not combo_str or not combo_str.strip():
        return None
    parts = [p.strip().upper() for p in combo_str.split("+") if p.strip()]
    if not parts:
        return None

    mods: list[int] = []
    primary: Optional[int] = None
    for part in parts:
        if part in MODIFIER_VKS:
            vk = MODIFIER_VKS[part]
            if vk not in mods:
                mods.append(vk)
        else:
            primary = VK_MAP.get(part)
            if primary is None and len(part) == 1:
                primary = ord(part)

    if primary is None:
        return None
    return tuple(mods), primary


class MultiHotkeyMonitor(QObject):
    """Hook-free global hotkey manager supporting multiple named actions."""

    action_triggered = pyqtSignal(str)

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._bindings: dict[str, tuple[tuple[int, ...], int]] = {}
        self._was_down: dict[str, bool] = {}
        self.paused: bool = False

        self._timer = QTimer(self)
        self._timer.setInterval(40)
        self._timer.timeout.connect(self._poll)
        if sys.platform == "win32":
            self._timer.start()

    def set_binding(self, action_name: str, combo_str: str) -> None:
        parsed = parse_hotkey_binding(combo_str)
        if parsed is None:
            self._bindings.pop(action_name, None)
            self._was_down.pop(action_name, None)
        else:
            self._bindings[action_name] = parsed
            self._was_down.setdefault(action_name, False)

    def stop(self) -> None:
        self._timer.stop()

    def _is_vk_down(self, vk: int) -> bool:
        return bool(ctypes.windll.user32.GetAsyncKeyState(vk) & 0x8000)

    def _poll(self) -> None:
        if self.paused or not self._bindings:
            return
        for action_name, (mods, primary_vk) in list(self._bindings.items()):
            primary_down = self._is_vk_down(primary_vk)
            mods_down = all(self._is_vk_down(m) for m in mods)
            active_now = primary_down and mods_down
            if active_now and not self._was_down.get(action_name, False):
                self.action_triggered.emit(action_name)
            self._was_down[action_name] = active_now
