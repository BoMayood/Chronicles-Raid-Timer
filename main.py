"""Application bootstrap and runtime orchestrator for Chronicles Raid Timer v0.6."""

from __future__ import annotations

import os
import sys
import time
from typing import Optional

from PyQt6.QtCore import QObject, QTimer
from PyQt6.QtGui import QAction, QIcon
from PyQt6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from chronicles.audio_engine import AudioEngine, format_tts_callout
from chronicles.config import AppConfig, get_app_root, get_resource_root, load_config, save_config
from chronicles.hotkey_manager import MultiHotkeyMonitor
from chronicles.models import RaidStatus
from chronicles.themes import get_theme
from chronicles.ui.command_center import CommandCenterWindow
from chronicles.ui.hud_overlay import ChroniclesHudOverlay
from chronicles.ui.svg_icons import render_svg_icon
from chronicles.ui.toast_banner import RaidToastBanner
from chronicles.win32_utils import SingleInstanceGuard, init_windows_platform
from version import APP_MUTEX_NAME, APP_NAME, APP_VERSION


class ChroniclesController(QObject):
    """Coordinates HUD overlay, Command Center, Tray, Hotkeys, Alerts, and TTS."""

    def __init__(self, cfg: Optional[AppConfig] = None):
        super().__init__()
        self.cfg = cfg or load_config()
        self.audio = AudioEngine()
        self.triggered_alerts: set[tuple[str, float, int]] = set()
        self.snoozed_until: dict[str, float] = {}
        self._last_statuses: list[RaidStatus] = []

        self.hud = ChroniclesHudOverlay(self.cfg)
        self.hud.set_snoozed_map(self.snoozed_until)
        self.toast = RaidToastBanner()
        self.cmd_center: Optional[CommandCenterWindow] = None

        self.hotkeys = MultiHotkeyMonitor(self)
        self.hotkeys.action_triggered.connect(self._on_hotkey)
        self._sync_hotkeys()

        self._setup_tray()
        self._wire_signals()

        self.tick_timer = QTimer(self)
        self.tick_timer.setInterval(1000)
        self.tick_timer.timeout.connect(self._on_tick)
        self.tick_timer.start()
        self._on_tick()

    def _wire_signals(self) -> None:
        self.hud.command_center_requested.connect(self.open_command_center)
        self.hud.snooze_raid_requested.connect(self.toggle_snooze_raid)
        self.hud.manual_reset_requested.connect(self.reset_manual_raid)
        self.hud.config_changed.connect(self._on_config_changed)
        self.hud.hide_to_tray_requested.connect(self.hide_hud)
        self.hud.quit_requested.connect(self.quit_app)

    def _setup_tray(self) -> None:
        icon = render_svg_icon("crest", 24, "#F5C451", "#22D3EE")
        for candidate in (
            os.path.join(get_resource_root(), "assets", "icons", "app_icon.ico"),
            os.path.join(get_app_root(), "assets", "icons", "app_icon.ico"),
        ):
            if os.path.exists(candidate):
                icon = QIcon(candidate)
                break

        self.tray = QSystemTrayIcon(icon, self)
        self.tray.setToolTip(f"{APP_NAME} v{APP_VERSION}")
        menu = QMenu()
        self._act_show = QAction("Show / Hide HUD", menu)
        self._act_show.triggered.connect(self.toggle_hud_visibility)
        menu.addAction(self._act_show)

        self._act_lock = QAction("Toggle Ghost Lock", menu)
        self._act_lock.triggered.connect(self.hud.toggle_lock)
        menu.addAction(self._act_lock)

        self._act_cmd = QAction("Open Command Center", menu)
        self._act_cmd.triggered.connect(self.open_command_center)
        menu.addAction(self._act_cmd)

        menu.addSeparator()
        act_quit = QAction("Quit", menu)
        act_quit.triggered.connect(self.quit_app)
        menu.addAction(act_quit)

        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self._on_tray_activated)
        if QSystemTrayIcon.isSystemTrayAvailable():
            self.tray.show()

    def _on_tray_activated(self, reason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.toggle_hud_visibility()

    def show_hud(self) -> None:
        self.hud.show()

    def hide_hud(self) -> None:
        if self.cfg.minimize_to_tray and QSystemTrayIcon.isSystemTrayAvailable():
            self.hud.hide()
        else:
            self.hud.showMinimized()

    def toggle_hud_visibility(self) -> None:
        if self.hud.isVisible():
            self.hide_hud()
        else:
            self.hud.show()
            self.hud.raise_()

    def open_command_center(self) -> None:
        if self.hud.is_locked:
            self.hud.toggle_lock()
        self.hotkeys.paused = True
        if self.cmd_center is None:
            self.cmd_center = CommandCenterWindow(self.cfg, self.audio)
            self.cmd_center.config_updated.connect(self._on_config_changed)
            self.cmd_center.test_toast_requested.connect(self._show_preview_toast)
        else:
            self.cmd_center.reload_from_config(self.cfg)
        self.cmd_center.show()
        self.cmd_center.raise_()
        self.cmd_center.activateWindow()

    def _on_config_changed(self, new_cfg: AppConfig) -> None:
        self.cfg = new_cfg
        self._sync_hotkeys()
        self.hud.apply_config(self.cfg, resize_fit=True)

    def _sync_hotkeys(self) -> None:
        self.hotkeys.set_binding("lock", self.cfg.hotkey_lock)
        self.hotkeys.set_binding("toggle_hud", self.cfg.hotkey_toggle_hud)
        self.hotkeys.set_binding("compact", self.cfg.hotkey_compact)
        self.hotkeys.set_binding("snooze", self.cfg.hotkey_snooze)

    def _on_hotkey(self, action: str) -> None:
        if self.cmd_center is not None and self.cmd_center.isVisible():
            return
        if action == "lock":
            self.hud.toggle_lock()
        elif action == "toggle_hud":
            self.toggle_hud_visibility()
        elif action == "compact":
            self.hud.cycle_hud_mode()
        elif action == "snooze":
            self.snooze_next_imminent()

    def toggle_snooze_raid(self, raid_id: str) -> None:
        now = time.time()
        if self.snoozed_until.get(raid_id, 0.0) > now:
            self.snoozed_until.pop(raid_id, None)
        else:
            # Snooze for 35 minutes (covers current alert/phase cycle)
            self.snoozed_until[raid_id] = now + 35 * 60
        self._on_tick()

    def snooze_next_imminent(self) -> None:
        for st in self._last_statuses:
            if st.is_imminent or st.is_active:
                self.snoozed_until[st.raid.id] = time.time() + 35 * 60
                break
        self._on_tick()

    def reset_manual_raid(self, raid_id: str) -> None:
        now = time.time()
        for r in self.cfg.raids:
            if r.id == raid_id and r.schedule_kind == "interval_manual":
                r.manual_target_ts = now + r.interval_minutes * 60
                break
        save_config(self.cfg)
        self._on_tick()

    def _on_tick(self) -> None:
        now = time.time()
        if self.cmd_center is None or not self.cmd_center.isVisible():
            self.hotkeys.paused = False

        statuses = self.hud.refresh_tick(now)
        self._last_statuses = statuses
        self._evaluate_alerts(statuses, now)

        if len(self.triggered_alerts) > 40:
            self.triggered_alerts = {k for k in self.triggered_alerts if now - k[1] < 86400}

        if statuses and self.tray.isVisible():
            top = statuses[0]
            state_txt = "LIVE" if top.is_active else "Next"
            self.tray.setToolTip(f"{APP_NAME} v{APP_VERSION}\n{state_txt}: {top.raid.name} ({top.phase_label})")

    def _evaluate_alerts(self, statuses: list[RaidStatus], now: float) -> None:
        for st in statuses:
            if not st.is_configured or st.is_snoozed:
                continue
            raid = st.raid

            # Upcoming milestones (e.g. 15m, 5m, 1m before start)
            if st.next_window is not None:
                win = st.next_window
                if win.is_hard and not self.cfg.alert_on_hard_transition:
                    pass
                else:
                    sec_left = int(win.start_ts - now)
                    for mins in self.cfg.alert_milestones:
                        if mins <= 0:
                            continue
                        offset = mins * 60
                        if 0 <= sec_left <= offset and (offset - sec_left) <= 12:
                            key = (raid.id, win.start_ts, mins)
                            if key not in self.triggered_alerts:
                                self.triggered_alerts.add(key)
                                self._fire_notification(
                                    title=raid.name,
                                    badge=f"{mins}M WARNING",
                                    message=f"{win.phase_label} phase begins in {mins} minute{'s' if mins > 1 else ''}",
                                    icon_key=raid.icon_key,
                                    accent=raid.accent_color,
                                    phase_label=win.phase_label,
                                    minutes_left=mins,
                                )

            # At start / Phase transition (0m)
            if 0 in self.cfg.alert_milestones and st.is_active and st.active_window is not None:
                win = st.active_window
                if win.is_hard and not self.cfg.alert_on_hard_transition:
                    continue
                elapsed = now - win.start_ts
                if 0 <= elapsed <= 6:
                    key = (raid.id, win.start_ts, 0)
                    if key not in self.triggered_alerts:
                        self.triggered_alerts.add(key)
                        self._fire_notification(
                            title=raid.name,
                            badge=f"LIVE • {win.phase_label.upper()}",
                            message=f"{win.phase_label} phase is now active!",
                            icon_key=raid.icon_key,
                            accent=raid.accent_color,
                            phase_label=win.phase_label,
                            minutes_left=0,
                        )

    def _fire_notification(
        self,
        title: str,
        badge: str,
        message: str,
        icon_key: str,
        accent: str,
        phase_label: str = "",
        minutes_left: Optional[int] = None,
    ) -> None:
        if self.cfg.sound_enabled:
            self.audio.play_sound(self.cfg.sound_file, self.cfg.volume)
        if self.cfg.tts_enabled:
            spoken = format_tts_callout(
                self.cfg.tts_style,
                title=title,
                message=message,
                phase_label=phase_label,
                minutes_left=minutes_left,
            )
            self.audio.speak(
                spoken,
                volume_percent=self.cfg.tts_volume,
                rate=self.cfg.tts_rate,
                pitch=self.cfg.tts_pitch,
                voice_id=self.cfg.tts_voice,
            )
        if self.cfg.toast_enabled:
            self.toast.show_alert(
                title=title,
                badge=badge,
                message=message,
                icon_key=icon_key,
                accent_hex=accent,
                theme=get_theme(self.cfg.theme),
                corner=self.cfg.toast_position,
            )

    def _show_preview_toast(self) -> None:
        self.toast.show_alert(
            title="Crimson Rift",
            badge="5M WARNING",
            message="Normal phase begins in 5 minutes",
            icon_key="rift",
            accent_hex="#FF476F",
            theme=get_theme(self.cfg.theme),
            corner=self.cfg.toast_position,
        )

    def quit_app(self) -> None:
        self.tick_timer.stop()
        self.hotkeys.stop()
        save_config(self.cfg)
        if self.cmd_center:
            self.cmd_center.close()
        self.toast.close()
        self.tray.hide()
        self.hud.close()
        QApplication.quit()


def main() -> int:
    init_windows_platform()

    if "--uninstall" in sys.argv:
        from chronicles.ui.uninstaller_wizard import UninstallerWizard, run_silent_uninstall

        if "--silent" in sys.argv:
            return run_silent_uninstall()
        app = QApplication(sys.argv)
        app.setApplicationName(APP_NAME)
        app.setApplicationVersion(APP_VERSION)
        wizard = UninstallerWizard()
        wizard.show()
        return app.exec()

    guard = SingleInstanceGuard(APP_MUTEX_NAME)
    if guard.already_running:
        return 0

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    app.setQuitOnLastWindowClosed(False)

    controller = ChroniclesController()
    controller.show_hud()
    code = app.exec()
    guard.release()
    return code


if __name__ == "__main__":
    sys.exit(main())
