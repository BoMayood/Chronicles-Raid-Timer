"""Modern 4-step Setup Wizard installer for Chronicles Raid Timer v0.6."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import zipfile
from typing import Optional

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont, QIcon
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from chronicles.config import get_resource_root
from chronicles.themes import get_theme
from chronicles.ui.svg_icons import render_svg_pixmap
from chronicles.win32_utils import (
    create_windows_shortcut,
    init_windows_platform,
    register_windows_uninstall,
    set_windows_startup,
    terminate_other_app_instances,
)
from version import APP_AUTHOR, APP_NAME, APP_VERSION


def _find_payload_zip() -> Optional[str]:
    candidates = [
        os.path.join(get_resource_root(), "payload.zip"),
        os.path.join(ROOT, "build", "payload.zip"),
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    return None


class InstallWorker(QThread):
    """Background installation thread extracting payload and configuring shortcuts cleanly."""

    progress = pyqtSignal(int, str)
    finished_ok = pyqtSignal(str)
    failed = pyqtSignal(str)

    def __init__(
        self,
        payload_zip: str,
        install_dir: str,
        desktop_shortcut: bool,
        start_menu_shortcut: bool,
        register_uninstall: bool,
        run_at_startup: bool,
    ):
        super().__init__()
        self.payload_zip = payload_zip
        self.install_dir = install_dir
        self.desktop_shortcut = desktop_shortcut
        self.start_menu_shortcut = start_menu_shortcut
        self.register_uninstall = register_uninstall
        self.run_at_startup = run_at_startup

    def run(self) -> None:
        try:
            self.progress.emit(6, "Checking for running Chronicles Raid Timer instances...")
            closed = terminate_other_app_instances("ChroniclesRaidTimer.exe")
            if closed:
                self.progress.emit(12, f"Closed {closed} running background instance(s).")

            self.progress.emit(16, f"Preparing target folder: {self.install_dir}")
            os.makedirs(self.install_dir, exist_ok=True)

            # Remove previous _internal folder cleanly on upgrade
            internal_dir = os.path.join(self.install_dir, "_internal")
            if os.path.exists(internal_dir):
                shutil.rmtree(internal_dir, ignore_errors=True)

            with zipfile.ZipFile(self.payload_zip, "r") as zf:
                members = zf.infolist()
                total = max(1, len(members))
                for idx, member in enumerate(members):
                    zf.extract(member, self.install_dir)
                    if idx % 20 == 0 or idx == total - 1:
                        pct = 18 + int(62.0 * (idx + 1) / total)
                        self.progress.emit(pct, f"Extracting ({idx + 1}/{total}): {member.filename}")

            exe_path = os.path.join(self.install_dir, "ChroniclesRaidTimer.exe")
            icon_path = os.path.join(self.install_dir, "app_icon.ico")
            if not os.path.exists(icon_path):
                alt_icon = os.path.join(self.install_dir, "_internal", "assets", "icons", "app_icon.ico")
                if os.path.exists(alt_icon):
                    shutil.copy2(alt_icon, icon_path)

            if self.desktop_shortcut:
                desktop_lnk = os.path.join(os.path.expanduser("~"), "Desktop", f"{APP_NAME}.lnk")
                create_windows_shortcut(
                    target_path=exe_path,
                    link_path=desktop_lnk,
                    description=f"{APP_NAME} v{APP_VERSION} HUD Overlay",
                    working_dir=self.install_dir,
                    icon_path=icon_path,
                )
                self.progress.emit(86, "Created Desktop shortcut via Windows COM.")

            if self.start_menu_shortcut:
                sm_dir = os.path.join(
                    os.environ.get("APPDATA", ""),
                    "Microsoft",
                    "Windows",
                    "Start Menu",
                    "Programs",
                    APP_NAME,
                )
                os.makedirs(sm_dir, exist_ok=True)
                create_windows_shortcut(
                    target_path=exe_path,
                    link_path=os.path.join(sm_dir, f"{APP_NAME}.lnk"),
                    description=f"{APP_NAME} v{APP_VERSION}",
                    working_dir=self.install_dir,
                    icon_path=icon_path,
                )
                create_windows_shortcut(
                    target_path=exe_path,
                    link_path=os.path.join(sm_dir, f"Uninstall {APP_NAME}.lnk"),
                    arguments="--uninstall",
                    description=f"Uninstall {APP_NAME}",
                    working_dir=self.install_dir,
                    icon_path=icon_path,
                )
                self.progress.emit(92, "Created Start Menu shortcuts & Uninstaller link.")

            if self.register_uninstall:
                total_bytes = 0
                for root_d, _, files in os.walk(self.install_dir):
                    for fn in files:
                        try:
                            total_bytes += os.path.getsize(os.path.join(root_d, fn))
                        except OSError:
                            pass
                register_windows_uninstall(
                    install_dir=self.install_dir,
                    exe_path=exe_path,
                    icon_path=icon_path,
                    estimated_kb=max(1024, total_bytes // 1024),
                )
                self.progress.emit(96, "Registered in Windows Installed Apps (Add/Remove Programs).")

            if self.run_at_startup:
                set_windows_startup(True, exe_override=exe_path)
                self.progress.emit(99, "Configured Windows Startup entry.")

            self.progress.emit(100, "Installation completed cleanly!")
            self.finished_ok.emit(exe_path)
        except Exception as exc:
            self.failed.emit(str(exc))


class ChroniclesInstallerWizard(QWidget):
    """Multi-page Setup Wizard for Chronicles Raid Timer."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.theme = get_theme("Obsidian Gold")
        local_appdata = os.environ.get(
            "LOCALAPPDATA", os.path.join(os.path.expanduser("~"), "AppData", "Local")
        )
        self.default_dir = os.path.join(local_appdata, "Programs", APP_NAME)
        self.installed_exe_path: str = ""
        self._worker: Optional[InstallWorker] = None

        self.setWindowTitle(f"{APP_NAME} Setup — v{APP_VERSION}")
        self.setFixedSize(730, 470)
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.WindowCloseButtonHint)

        for candidate in (
            os.path.join(get_resource_root(), "assets", "icons", "app_icon.ico"),
            os.path.join(ROOT, "assets", "icons", "app_icon.ico"),
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

        # Left Step Sidebar
        self.sidebar = QFrame(self)
        self.sidebar.setFixedWidth(212)
        side = QVBoxLayout(self.sidebar)
        side.setContentsMargins(16, 20, 16, 16)
        side.setSpacing(10)

        brand_row = QHBoxLayout()
        brand_row.setSpacing(9)
        logo = QLabel()
        logo.setPixmap(render_svg_pixmap("crest", 32))
        brand_row.addWidget(logo)
        b_col = QVBoxLayout()
        b_col.setSpacing(0)
        b_title = QLabel("CHRONICLES")
        b_title.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        b_col.addWidget(b_title)
        b_sub = QLabel(f"Setup Wizard • v{APP_VERSION}")
        b_sub.setFont(QFont("Segoe UI", 8))
        b_sub.setStyleSheet(f"color: {self.theme.accent_primary};")
        b_col.addWidget(b_sub)
        brand_row.addLayout(b_col)
        side.addLayout(brand_row)
        side.addSpacing(16)

        self._step_labels: list[QLabel] = []
        steps = [
            "1. Welcome",
            "2. Install Options",
            "3. Installing",
            "4. Complete",
        ]
        for st in steps:
            lbl = QLabel(st)
            lbl.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
            side.addWidget(lbl)
            self._step_labels.append(lbl)

        side.addStretch(1)
        note = QLabel("Clean Per-User Install\nZero Admin Elevation Needed")
        note.setFont(QFont("Segoe UI", 8))
        note.setStyleSheet(f"color: {self.theme.text_muted};")
        side.addWidget(note)
        credit = QLabel(f"Developed by {APP_AUTHOR}")
        credit.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        credit.setStyleSheet(f"color: {self.theme.accent_secondary};")
        side.addWidget(credit)
        outer.addWidget(self.sidebar)

        # Right Workspace + Bottom Buttons
        right = QVBoxLayout()
        right.setContentsMargins(22, 18, 22, 16)
        right.setSpacing(12)

        self.stack = QStackedWidget(self)
        self.stack.addWidget(self._build_welcome_page())
        self.stack.addWidget(self._build_options_page())
        self.stack.addWidget(self._build_installing_page())
        self.stack.addWidget(self._build_complete_page())
        right.addWidget(self.stack, 1)

        nav = QHBoxLayout()
        self.back_btn = QPushButton("Back")
        self.back_btn.setFixedHeight(33)
        self.back_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.back_btn.clicked.connect(self._go_back)
        nav.addWidget(self.back_btn)

        nav.addStretch(1)

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setFixedHeight(33)
        self.cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.cancel_btn.clicked.connect(self.close)
        nav.addWidget(self.cancel_btn)

        self.next_btn = QPushButton("Next")
        self.next_btn.setFixedHeight(33)
        self.next_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.next_btn.clicked.connect(self._go_next)
        nav.addWidget(self.next_btn)
        right.addLayout(nav)

        outer.addLayout(right, 1)
        self._set_step(0)

    def _build_welcome_page(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(12)

        title = QLabel(f"Welcome to {APP_NAME} v{APP_VERSION}")
        title.setFont(QFont("Segoe UI", 15, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {self.theme.accent_primary};")
        lay.addWidget(title)

        intro = QLabel(
            "Install the modern glassmorphic raid HUD overlay, 24-hour visual Command Center, "
            "curated audio alerts, and multi-voice Windows TTS announcer on your PC."
        )
        intro.setWordWrap(True)
        lay.addWidget(intro)

        card = QFrame()
        card.setProperty("role", "panel")
        c_lay = QVBoxLayout(card)
        c_lay.setContentsMargins(14, 12, 14, 12)
        c_lay.setSpacing(7)

        for hdr, body in [
            ("Adaptive Glassmorphic HUD", "3 display modes, Ghost Pass-Through Lock, and responsive compact sizing."),
            ("Chronicles Command Center", "24h swimlane timeline, custom Daily/Weekly/Respawn raids, and 6 themes."),
            ("Curated Audio & Voice TTS", "5 crisp HD alert cues, toast notifications, and 3 natural announcer personas."),
            ("Clean Windows Integration", "Fast per-user installation with standard Windows Apps uninstaller support."),
        ]:
            row_lbl = QLabel(f"<b style='color:{self.theme.accent_secondary};'>{hdr}</b> — {body}")
            row_lbl.setWordWrap(True)
            c_lay.addWidget(row_lbl)

        lay.addWidget(card)

        self.license_chk = QCheckBox("I accept the MIT License terms and wish to continue")
        self.license_chk.setChecked(True)
        self.license_chk.toggled.connect(lambda ok: self.next_btn.setEnabled(ok))
        lay.addWidget(self.license_chk)
        lay.addStretch(1)
        return page

    def _build_options_page(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(12)

        title = QLabel("Destination & Installation Options")
        title.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {self.theme.accent_primary};")
        lay.addWidget(title)

        c_dest = QFrame()
        c_dest.setProperty("role", "panel")
        d_lay = QVBoxLayout(c_dest)
        d_lay.setContentsMargins(14, 12, 14, 12)
        d_lay.setSpacing(8)

        d_lay.addWidget(QLabel("Installation Folder:"))
        path_row = QHBoxLayout()
        self.path_edit = QLineEdit(self.default_dir)
        path_row.addWidget(self.path_edit, 1)
        browse_btn = QPushButton("Browse...")
        browse_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        browse_btn.clicked.connect(self._browse_dir)
        path_row.addWidget(browse_btn)
        d_lay.addLayout(path_row)

        hint = QLabel("Recommended per-user location — requires no administrator privileges.")
        hint.setStyleSheet(f"color: {self.theme.text_muted}; font-size: 10px;")
        d_lay.addWidget(hint)
        lay.addWidget(c_dest)

        c_opts = QFrame()
        c_opts.setProperty("role", "panel")
        o_lay = QVBoxLayout(c_opts)
        o_lay.setContentsMargins(14, 12, 14, 12)
        o_lay.setSpacing(8)

        self.chk_desktop = QCheckBox("Create Desktop shortcut")
        self.chk_desktop.setChecked(True)
        self.chk_start_menu = QCheckBox("Create Start Menu folder && Uninstaller shortcut")
        self.chk_start_menu.setChecked(True)
        self.chk_reg_uninstall = QCheckBox("Register in Windows Installed Apps (Add/Remove Programs)")
        self.chk_reg_uninstall.setChecked(True)
        self.chk_startup = QCheckBox("Launch automatically when Windows starts")
        self.chk_startup.setChecked(False)

        for cb in (self.chk_desktop, self.chk_start_menu, self.chk_reg_uninstall, self.chk_startup):
            o_lay.addWidget(cb)
        lay.addWidget(c_opts)
        lay.addStretch(1)
        return page

    def _build_installing_page(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)

        title = QLabel("Installing Chronicles Raid Timer...")
        title.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {self.theme.accent_primary};")
        lay.addWidget(title)

        self.inst_status_lbl = QLabel("Starting installation...")
        lay.addWidget(self.inst_status_lbl)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        lay.addWidget(self.progress)

        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setFont(QFont("Consolas", 9))
        lay.addWidget(self.log_view, 1)
        return page

    def _build_complete_page(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(12)

        title = QLabel("Installation Complete!")
        title.setFont(QFont("Segoe UI", 15, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {self.theme.live_normal_fg};")
        lay.addWidget(title)

        card = QFrame()
        card.setProperty("role", "panel")
        c_lay = QVBoxLayout(card)
        c_lay.setContentsMargins(14, 14, 14, 14)
        c_lay.setSpacing(8)

        self.complete_lbl = QLabel()
        self.complete_lbl.setWordWrap(True)
        c_lay.addWidget(self.complete_lbl)

        self.chk_launch = QCheckBox(f"Launch {APP_NAME} now")
        self.chk_launch.setChecked(True)
        c_lay.addWidget(self.chk_launch)

        lay.addWidget(card)
        lay.addStretch(1)
        return page

    def _browse_dir(self) -> None:
        chosen = QFileDialog.getExistingDirectory(self, "Select Installation Folder", self.path_edit.text())
        if chosen:
            if not chosen.rstrip("\\/").endswith(APP_NAME):
                chosen = os.path.join(chosen, APP_NAME)
            self.path_edit.setText(chosen)

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

        self.back_btn.setVisible(idx == 1)
        self.cancel_btn.setVisible(idx in (0, 1))
        if idx == 0:
            self.next_btn.setText("Next")
            self.next_btn.setEnabled(self.license_chk.isChecked())
        elif idx == 1:
            self.next_btn.setText("Install Now")
            self.next_btn.setEnabled(True)
        elif idx == 2:
            self.next_btn.setText("Installing...")
            self.next_btn.setEnabled(False)
        else:
            self.next_btn.setText("Finish")
            self.next_btn.setEnabled(True)

    def _go_back(self) -> None:
        if self.stack.currentIndex() == 1:
            self._set_step(0)

    def _go_next(self) -> None:
        idx = self.stack.currentIndex()
        if idx == 0:
            self._set_step(1)
        elif idx == 1:
            self._begin_install()
        elif idx == 3:
            if self.chk_launch.isChecked() and self.installed_exe_path and os.path.exists(self.installed_exe_path):
                try:
                    subprocess.Popen(
                        [self.installed_exe_path],
                        cwd=os.path.dirname(self.installed_exe_path),
                    )
                except Exception:
                    pass
            self.close()
            QApplication.quit()

    def _begin_install(self) -> None:
        target = self.path_edit.text().strip()
        if not target:
            QMessageBox.warning(self, "Invalid Path", "Please choose an installation folder.")
            return
        payload = _find_payload_zip()
        if not payload:
            QMessageBox.critical(
                self,
                "Missing Payload",
                "Application payload archive (payload.zip) was not found in the setup package.",
            )
            return

        self._set_step(2)
        self.log_view.clear()
        self._worker = InstallWorker(
            payload_zip=payload,
            install_dir=target,
            desktop_shortcut=self.chk_desktop.isChecked(),
            start_menu_shortcut=self.chk_start_menu.isChecked(),
            register_uninstall=self.chk_reg_uninstall.isChecked(),
            run_at_startup=self.chk_startup.isChecked(),
        )
        self._worker.progress.connect(self._on_progress)
        self._worker.finished_ok.connect(self._on_finished)
        self._worker.failed.connect(self._on_failed)
        self._worker.start()

    def _on_progress(self, pct: int, msg: str) -> None:
        self.progress.setValue(pct)
        self.inst_status_lbl.setText(msg)
        self.log_view.appendPlainText(f"[{pct:3d}%] {msg}")

    def _on_finished(self, exe_path: str) -> None:
        self.installed_exe_path = exe_path
        self.complete_lbl.setText(
            f"{APP_NAME} v{APP_VERSION} has been successfully installed to:\n\n"
            f"{os.path.dirname(exe_path)}\n\n"
            "You can uninstall anytime from Windows Settings → Apps or the Start Menu."
        )
        self._set_step(3)

    def _on_failed(self, err: str) -> None:
        QMessageBox.critical(self, "Installation Failed", f"An error occurred during installation:\n{err}")
        self._set_step(1)

    def _apply_styles(self) -> None:
        t = self.theme
        self.setStyleSheet(
            f"""
            QWidget {{ background: {t.bg_primary}; color: {t.text_primary}; font-family: 'Segoe UI'; }}
            QFrame[role="panel"] {{
                background: {t.card_bg}; border: 1px solid {t.border_subtle}; border-radius: 10px;
            }}
            QLabel {{ background: transparent; color: {t.text_secondary}; font-size: 11px; }}
            QLineEdit {{
                background: {t.bg_elevated}; color: {t.text_primary};
                border: 1px solid {t.border_subtle}; border-radius: 6px; padding: 5px 8px;
                font-family: 'Consolas'; font-size: 10px;
            }}
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
                text-align: center; color: {t.text_primary}; font-weight: bold; height: 19px;
            }}
            QProgressBar::chunk {{ background: {t.accent_primary}; border-radius: 5px; }}
            QPlainTextEdit {{
                background: {t.bg_elevated}; color: {t.text_secondary};
                border: 1px solid {t.border_subtle}; border-radius: 8px; padding: 6px;
            }}
            QPushButton {{
                background: {t.bg_elevated}; color: {t.text_primary};
                border: 1px solid {t.border_subtle}; border-radius: 7px; padding: 6px 16px; font-weight: bold;
            }}
            QPushButton:hover {{ border: 1px solid {t.accent_primary}; color: {t.accent_primary}; }}
            """
        )
        self.sidebar.setStyleSheet(
            f"background: {t.bg_elevated}; border-right: 1px solid {t.border_subtle};"
        )
        self.next_btn.setStyleSheet(
            f"background: {t.accent_primary}; color: #0B0E14; border: none; border-radius: 7px; padding: 6px 20px;"
        )


def main() -> int:
    init_windows_platform()
    app = QApplication(sys.argv)
    app.setApplicationName(f"{APP_NAME} Setup")
    app.setApplicationVersion(APP_VERSION)
    wiz = ChroniclesInstallerWizard()
    wiz.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
