"""Modern multi-step Uninstaller Wizard for Chronicles Raid Timer."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from typing import Optional

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont, QIcon
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from chronicles.config import get_app_root, get_data_dir, get_resource_root
from chronicles.themes import get_theme
from chronicles.ui.svg_icons import render_svg_pixmap
from chronicles.win32_utils import (
    set_windows_startup,
    terminate_other_app_instances,
    unregister_windows_uninstall,
)
from version import APP_AUTHOR, APP_NAME, APP_VERSION


def get_shortcut_locations() -> tuple[str, str]:
    desktop = os.path.join(os.path.expanduser("~"), "Desktop", f"{APP_NAME}.lnk")
    start_menu_dir = os.path.join(
        os.environ.get("APPDATA", ""),
        "Microsoft",
        "Windows",
        "Start Menu",
        "Programs",
        APP_NAME,
    )
    return desktop, start_menu_dir


class UninstallerWizard(QWidget):
    """Sleek Obsidian-themed Uninstaller Wizard matching Chronicles design language."""

    def __init__(self, install_dir: Optional[str] = None, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.theme = get_theme("Obsidian Gold")
        self.install_dir = install_dir or get_app_root()
        self.user_data_dir = get_data_dir()
        self.is_frozen = getattr(sys, "frozen", False)
        self._removed_program_dir = False

        self.setWindowTitle(f"{APP_NAME} — Uninstall v{APP_VERSION}")
        self.setFixedSize(640, 420)
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.WindowCloseButtonHint)

        for candidate in (
            os.path.join(get_resource_root(), "assets", "icons", "app_icon.ico"),
            os.path.join(self.install_dir, "app_icon.ico"),
        ):
            if os.path.exists(candidate):
                self.setWindowIcon(QIcon(candidate))
                break

        self._build_ui()
        self._apply_styles()

    def _build_ui(self) -> None:
        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Left Brand & Step Rail
        self.sidebar = QFrame(self)
        self.sidebar.setFixedWidth(200)
        side = QVBoxLayout(self.sidebar)
        side.setContentsMargins(16, 20, 16, 16)
        side.setSpacing(10)

        brand_row = QHBoxLayout()
        brand_row.setSpacing(8)
        logo = QLabel()
        logo.setPixmap(render_svg_pixmap("crest", 28))
        brand_row.addWidget(logo)
        b_col = QVBoxLayout()
        b_col.setSpacing(0)
        b_title = QLabel("CHRONICLES")
        b_title.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        b_col.addWidget(b_title)
        b_sub = QLabel(f"Uninstaller • v{APP_VERSION}")
        b_sub.setFont(QFont("Segoe UI", 8))
        b_sub.setStyleSheet(f"color: {self.theme.accent_primary};")
        b_col.addWidget(b_sub)
        brand_row.addLayout(b_col)
        side.addLayout(brand_row)
        side.addSpacing(14)

        self._step_labels: list[QLabel] = []
        for idx, text in enumerate(["1. Confirm Removal", "2. Uninstalling", "3. Finished"]):
            lbl = QLabel(text)
            lbl.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold if idx == 0 else QFont.Weight.Medium))
            side.addWidget(lbl)
            self._step_labels.append(lbl)

        side.addStretch(1)
        credit = QLabel(f"Developed by {APP_AUTHOR}")
        credit.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        credit.setStyleSheet(f"color: {self.theme.accent_secondary};")
        side.addWidget(credit)
        outer.addWidget(self.sidebar)

        # Right Content Stack
        right = QVBoxLayout()
        right.setContentsMargins(20, 18, 20, 16)
        right.setSpacing(12)

        self.stack = QStackedWidget(self)
        self.stack.addWidget(self._build_confirm_page())
        self.stack.addWidget(self._build_progress_page())
        self.stack.addWidget(self._build_done_page())
        right.addWidget(self.stack, 1)

        btn_bar = QHBoxLayout()
        btn_bar.addStretch(1)
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setFixedHeight(32)
        self.cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.cancel_btn.clicked.connect(self.close)
        btn_bar.addWidget(self.cancel_btn)

        self.action_btn = QPushButton("Uninstall")
        self.action_btn.setFixedHeight(32)
        self.action_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.action_btn.clicked.connect(self._on_action_clicked)
        btn_bar.addWidget(self.action_btn)
        right.addLayout(btn_bar)

        outer.addLayout(right, 1)
        self._set_step(0)

    def _build_confirm_page(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(12)

        title = QLabel(f"Uninstall {APP_NAME}")
        title.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        title.setStyleSheet("color: #FB7185;")
        lay.addWidget(title)

        desc = QLabel(
            f"This wizard will safely close any running overlay, unregister {APP_NAME} from "
            "Windows Installed Apps, and remove its shortcuts and program files."
        )
        desc.setWordWrap(True)
        lay.addWidget(desc)

        card = QFrame()
        card.setProperty("role", "panel")
        c_lay = QVBoxLayout(card)
        c_lay.setContentsMargins(14, 12, 14, 12)
        c_lay.setSpacing(8)

        loc_hdr = QLabel("Installed Folder:")
        loc_hdr.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        c_lay.addWidget(loc_hdr)

        loc_val = QLabel(self.install_dir)
        loc_val.setWordWrap(True)
        loc_val.setFont(QFont("Consolas", 9))
        loc_val.setStyleSheet(f"color: {self.theme.accent_secondary};")
        c_lay.addWidget(loc_val)

        self.chk_app = QCheckBox("Remove program executables, Desktop && Start Menu shortcuts")
        self.chk_app.setChecked(True)
        self.chk_app.setEnabled(False)
        c_lay.addWidget(self.chk_app)

        self.chk_data = QCheckBox(
            "Also delete user config, custom raids && imported sounds"
        )
        self.chk_data.setChecked(False)
        c_lay.addWidget(self.chk_data)

        lay.addWidget(card)
        lay.addStretch(1)
        return page

    def _build_progress_page(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)

        title = QLabel("Removing Chronicles Raid Timer...")
        title.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {self.theme.accent_primary};")
        lay.addWidget(title)

        self.status_lbl = QLabel("Preparing uninstallation...")
        lay.addWidget(self.status_lbl)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        lay.addWidget(self.progress)

        self.log_box = QPlainTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.setFont(QFont("Consolas", 9))
        lay.addWidget(self.log_box, 1)
        return page

    def _build_done_page(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(12)

        title = QLabel("Uninstallation Complete")
        title.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {self.theme.live_normal_fg};")
        lay.addWidget(title)

        card = QFrame()
        card.setProperty("role", "panel")
        c_lay = QVBoxLayout(card)
        c_lay.setContentsMargins(14, 14, 14, 14)
        c_lay.setSpacing(8)

        self.done_summary = QLabel(
            f"{APP_NAME} v{APP_VERSION} has been cleanly removed from your system."
        )
        self.done_summary.setWordWrap(True)
        c_lay.addWidget(self.done_summary)
        lay.addWidget(card)
        lay.addStretch(1)
        return page

    def _set_step(self, idx: int) -> None:
        self.stack.setCurrentIndex(idx)
        t = self.theme
        for i, lbl in enumerate(self._step_labels):
            if i == idx:
                lbl.setStyleSheet(f"color: {t.accent_primary}; font-weight: bold;")
            elif i < idx:
                lbl.setStyleSheet(f"color: {t.live_normal_fg};")
            else:
                lbl.setStyleSheet(f"color: {t.text_muted};")

    def _on_action_clicked(self) -> None:
        idx = self.stack.currentIndex()
        if idx == 0:
            self._start_uninstall()
        elif idx == 2:
            self._cleanup_and_exit()

    def _log(self, msg: str, pct: int) -> None:
        self.status_lbl.setText(msg)
        self.progress.setValue(pct)
        self.log_box.appendPlainText(f"• {msg}")

    def _start_uninstall(self) -> None:
        self._set_step(1)
        self.cancel_btn.setEnabled(False)
        self.action_btn.setEnabled(False)
        QTimer.singleShot(180, self._step_close_instances)

    def _step_close_instances(self) -> None:
        closed = terminate_other_app_instances("ChroniclesRaidTimer.exe")
        msg = f"Closed {closed} running instance(s)." if closed else "No background overlay running."
        self._log(msg, 20)
        QTimer.singleShot(180, self._step_registry_and_shortcuts)

    def _step_registry_and_shortcuts(self) -> None:
        set_windows_startup(False)
        unregister_windows_uninstall()
        self._log("Removed Windows Installed Apps & Startup entries.", 45)

        desktop_lnk, start_menu_dir = get_shortcut_locations()
        if os.path.exists(desktop_lnk):
            try:
                os.remove(desktop_lnk)
            except OSError:
                pass
        if os.path.exists(start_menu_dir):
            shutil.rmtree(start_menu_dir, ignore_errors=True)
        self._log("Removed Desktop & Start Menu shortcuts.", 68)
        QTimer.singleShot(180, self._step_files)

    def _step_files(self) -> None:
        if self.chk_data.isChecked() and os.path.exists(self.user_data_dir):
            if os.path.abspath(self.user_data_dir) != os.path.abspath(self.install_dir):
                shutil.rmtree(self.user_data_dir, ignore_errors=True)
                self._log(f"Deleted user configuration folder: {self.user_data_dir}", 82)

        # Safety: never delete source repository files when running uncompiled
        if self.is_frozen and os.path.exists(self.install_dir):
            for entry in os.listdir(self.install_dir):
                path = os.path.join(self.install_dir, entry)
                if entry.lower() == os.path.basename(sys.executable).lower():
                    continue
                if not self.chk_data.isChecked() and entry in ("config.json", "custom_sounds", "data"):
                    continue
                try:
                    if os.path.isdir(path):
                        shutil.rmtree(path, ignore_errors=True)
                    else:
                        os.remove(path)
                except OSError:
                    pass
            self._removed_program_dir = True
            self._log("Cleaned installed application files.", 100)
        else:
            self._log("Running from source mode — skipped deleting source workspace files.", 100)

        self._set_step(2)
        self.cancel_btn.setVisible(False)
        self.action_btn.setText("Finish")
        self.action_btn.setEnabled(True)
        self.action_btn.setStyleSheet(
            f"background: {self.theme.accent_primary}; color: #0B0E14; border: none; border-radius: 7px; padding: 6px 18px;"
        )

    def _cleanup_and_exit(self) -> None:
        if self._removed_program_dir and self.is_frozen and sys.platform == "win32":
            # Schedule clean removal of the locked executable & empty install directory after exit
            cmd = f'cmd.exe /c ping -n 3 127.0.0.1 >nul & rmdir /s /q "{self.install_dir}"'
            try:
                subprocess.Popen(cmd, shell=True, creationflags=0x08000000)
            except Exception:
                pass
        self.close()
        QApplication.quit()

    def _apply_styles(self) -> None:
        t = self.theme
        self.setStyleSheet(
            f"""
            QWidget {{ background: {t.bg_primary}; color: {t.text_primary}; font-family: 'Segoe UI'; }}
            QFrame[role="panel"] {{
                background: {t.card_bg}; border: 1px solid {t.border_subtle}; border-radius: 10px;
            }}
            QLabel {{ background: transparent; color: {t.text_secondary}; font-size: 11px; }}
            QCheckBox {{ background: transparent; color: {t.text_primary}; font-size: 11px; spacing: 8px; }}
            QCheckBox::indicator {{
                width: 15px; height: 15px; border-radius: 4px;
                border: 1.5px solid {t.border_subtle}; background: {t.bg_primary};
            }}
            QCheckBox::indicator:checked {{
                border: 1.5px solid {t.accent_primary}; background: {t.accent_primary};
            }}
            QProgressBar {{
                background: {t.bg_elevated}; border: 1px solid {t.border_subtle}; border-radius: 6px;
                text-align: center; color: {t.text_primary}; font-weight: bold; height: 18px;
            }}
            QProgressBar::chunk {{ background: #FB7185; border-radius: 5px; }}
            QPlainTextEdit {{
                background: {t.bg_elevated}; color: {t.text_secondary};
                border: 1px solid {t.border_subtle}; border-radius: 8px; padding: 6px;
            }}
            QPushButton {{
                background: {t.bg_elevated}; color: {t.text_primary};
                border: 1px solid {t.border_subtle}; border-radius: 7px; padding: 6px 16px; font-weight: bold;
            }}
            QPushButton:hover {{ border: 1px solid {t.accent_primary}; }}
            """
        )
        self.sidebar.setStyleSheet(
            f"background: {t.bg_elevated}; border-right: 1px solid {t.border_subtle};"
        )
        self.action_btn.setStyleSheet(
            "background: #E11D48; color: #FFFFFF; border: none; border-radius: 7px; padding: 6px 18px;"
        )


def run_silent_uninstall(install_dir: Optional[str] = None, remove_data: bool = False) -> int:
    """Perform unattended uninstallation for QuietUninstallString."""
    target = install_dir or get_app_root()
    terminate_other_app_instances("ChroniclesRaidTimer.exe")
    set_windows_startup(False)
    unregister_windows_uninstall()
    desktop_lnk, start_menu_dir = get_shortcut_locations()
    if os.path.exists(desktop_lnk):
        try:
            os.remove(desktop_lnk)
        except OSError:
            pass
    if os.path.exists(start_menu_dir):
        shutil.rmtree(start_menu_dir, ignore_errors=True)
    if remove_data:
        data_dir = get_data_dir()
        if os.path.exists(data_dir) and os.path.abspath(data_dir) != os.path.abspath(target):
            shutil.rmtree(data_dir, ignore_errors=True)
    if getattr(sys, "frozen", False) and os.path.exists(target):
        cmd = f'cmd.exe /c ping -n 3 127.0.0.1 >nul & rmdir /s /q "{target}"'
        subprocess.Popen(cmd, shell=True, creationflags=0x08000000)
    return 0
