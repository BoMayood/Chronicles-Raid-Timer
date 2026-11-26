"""Generate crisp showcase screenshots for README.md and GitHub presentation."""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont, QFontDatabase, QPainter, QPixmap
from PyQt6.QtWidgets import QApplication

from chronicles.audio_engine import AudioEngine
from chronicles.config import AppConfig
from chronicles.models import sample_preset_raids
from chronicles.themes import THEMES, get_theme
from chronicles.ui.command_center import CommandCenterWindow
from chronicles.ui.hud_overlay import ChroniclesHudOverlay
from chronicles.ui.toast_banner import RaidToastBanner
from chronicles.ui.uninstaller_wizard import UninstallerWizard

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from installer_wizard import ChroniclesInstallerWizard


def _load_windows_fonts() -> None:
    fonts_dir = r"C:\Windows\Fonts"
    for fname in ("segoeui.ttf", "segoeuib.ttf", "consola.ttf", "consolab.ttf"):
        fpath = os.path.join(fonts_dir, fname)
        if os.path.exists(fpath):
            QFontDatabase.addApplicationFont(fpath)


def _render_theme_gallery(out_path: str, sim_ts: float) -> None:
    theme_names = list(THEMES.keys())
    tiles: list[tuple[str, QPixmap]] = []
    for name in theme_names:
        cfg = AppConfig(theme=name, hud_mode="cards")
        hud = ChroniclesHudOverlay(cfg)
        hud.show()
        hud.refresh_tick(sim_ts)
        hud._sync_min_size(force_fit=True)
        tiles.append((name, hud.grab()))
        hud.close()

    cols = 2
    rows = (len(tiles) + 1) // 2
    pad = 24
    label_h = 26
    tile_w = max(pix.width() for _, pix in tiles)
    tile_h = max(pix.height() for _, pix in tiles)

    canvas_w = cols * tile_w + (cols + 1) * pad
    canvas_h = rows * (tile_h + label_h) + (rows + 1) * pad
    canvas = QPixmap(canvas_w, canvas_h)
    canvas.fill(QColor("#090C12"))

    painter = QPainter(canvas)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

    for idx, (name, pix) in enumerate(tiles):
        r, c = divmod(idx, cols)
        x = pad + c * (tile_w + pad)
        y = pad + r * (tile_h + label_h + pad)
        spec = THEMES[name]
        painter.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        painter.setPen(QColor(spec.accent_primary))
        painter.drawText(x + 4, y + 17, name)
        fm = painter.fontMetrics()
        name_w = fm.horizontalAdvance(name + "  ")
        painter.setFont(QFont("Segoe UI", 8))
        painter.setPen(QColor("#94A3B8"))
        desc_elided = painter.fontMetrics().elidedText(
            f"— {spec.description}", Qt.TextElideMode.ElideRight, tile_w - name_w - 8
        )
        painter.drawText(x + 4 + name_w, y + 17, desc_elided)
        painter.drawPixmap(x, y + label_h, pix)

    painter.end()
    canvas.save(out_path, "PNG")


def main() -> None:
    app = QApplication.instance() or QApplication(sys.argv)
    _load_windows_fonts()

    out_dir = os.path.join(ROOT, "docs", "screenshots")
    os.makedirs(out_dir, exist_ok=True)

    # Simulated timestamp: 03:55:12 UTC -> Crimson Rift LIVE (Hard, 4m48s left) & Nightmare SOON (4m48s)
    sim_ts = datetime(2026, 11, 26, 3, 55, 12, tzinfo=timezone.utc).timestamp()

    # 1. HUD Modes
    cfg = AppConfig(theme="Obsidian Gold", hud_mode="cards")
    hud = ChroniclesHudOverlay(cfg)
    hud.show()
    hud.refresh_tick(sim_ts)
    hud._sync_min_size(force_fit=True)
    hud.grab().save(os.path.join(out_dir, "hud_tactical_cards.png"), "PNG")

    cfg.hud_mode = "compact"
    hud.apply_config(cfg, resize_fit=True)
    hud.refresh_tick(sim_ts)
    hud._sync_min_size(force_fit=True)
    hud.grab().save(os.path.join(out_dir, "hud_compact_mode.png"), "PNG")

    cfg.hud_mode = "horizontal"
    hud.apply_config(cfg, resize_fit=True)
    hud.refresh_tick(sim_ts)
    hud._sync_min_size(force_fit=True)
    hud.grab().save(os.path.join(out_dir, "hud_horizontal_bar.png"), "PNG")
    hud.close()

    # 2. All 6 Themes Gallery
    _render_theme_gallery(os.path.join(out_dir, "hud_themes_gallery.png"), sim_ts)

    # 3. Command Center Tabs (include optional preset raids to showcase timeline + custom manager)
    cmd_cfg = AppConfig(theme="Obsidian Gold")
    presets = sample_preset_raids()
    presets[1].manual_target_ts = sim_ts + 3600 * 2.5
    cmd_cfg.raids.extend(presets)

    audio = AudioEngine()
    cmd = CommandCenterWindow(cmd_cfg, audio)
    cmd.show()

    tab_files = [
        (0, "command_center_timeline.png"),
        (1, "command_center_raids.png"),
        (2, "command_center_audio.png"),
        (3, "command_center_appearance.png"),
        (4, "command_center_hotkeys.png"),
    ]
    for idx, fname in tab_files:
        cmd._switch_tab(idx)
        if idx == 0:
            cmd._refresh_timeline(sim_ts)
        if idx == 4:
            from PyQt6.QtWidgets import QLabel

            for lbl in cmd.findChildren(QLabel):
                if lbl.text().startswith("Config Path:"):
                    lbl.setText("Config Path: %LOCALAPPDATA%\\ChroniclesRaidTimer\\config.json")
        cmd.grab().save(os.path.join(out_dir, fname), "PNG")
    cmd.close()

    # 4. Toast Banner
    toast = RaidToastBanner()
    toast.show_alert(
        title="Crimson Rift",
        badge="5M WARNING",
        message="Normal phase begins in 5 minutes",
        icon_key="rift",
        accent_hex="#FF476F",
        theme=get_theme("Obsidian Gold"),
    )
    toast.grab().save(os.path.join(out_dir, "toast_notification.png"), "PNG")
    toast.close()

    # 5. Setup & Uninstaller Wizards
    inst = ChroniclesInstallerWizard()
    inst.show()
    inst.path_edit.setText(r"%LOCALAPPDATA%\Programs\Chronicles Raid Timer")
    inst._set_step(1)
    app.processEvents()
    inst.grab().save(os.path.join(out_dir, "installer_wizard.png"), "PNG")
    inst.close()

    uninst = UninstallerWizard(install_dir=r"%LOCALAPPDATA%\Programs\Chronicles Raid Timer")
    uninst.show()
    uninst._set_step(0)
    app.processEvents()
    uninst.grab().save(os.path.join(out_dir, "uninstaller_wizard.png"), "PNG")
    uninst.close()

    print(f"Captured showcase screenshots in: {out_dir}")


if __name__ == "__main__":
    main()
