"""
ArcheAge Chronicles - Raid Timer Setup Wizard
Clean, modern installer wizard for ArcheAge Chronicles Raid Timer.

Created by NoYz
"""

import sys
import os
import json
import shutil
import subprocess

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont, QColor, QIcon
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, 
    QLabel, QPushButton, QFrame, QCheckBox, QProgressBar,
    QLineEdit, QFileDialog
)

class InstallerWizard(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("⚔️ ArcheAge Chronicles Raid Timer - Setup Wizard")
        self.setFixedSize(480, 360)
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
            QLineEdit {
                background-color: #1A2230;
                color: #EEE;
                border: 1px solid #2B384E;
                border-radius: 4px;
                padding: 5px 8px;
                font-size: 11px;
                font-family: Consolas;
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
                font-weight: bold;
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
                height: 18px;
            }
            QProgressBar::chunk {
                background-color: #00ADB5;
                border-radius: 3px;
            }
        """)

        # Package source directory (where installer is running from or bundled sys._MEIPASS)
        if getattr(sys, 'frozen', False):
            self.source_dir = getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
        else:
            self.source_dir = os.path.dirname(os.path.abspath(__file__))

        # Default installation target directory: %LOCALAPPDATA%\Programs\ArcheAge Raid Timer
        local_appdata = os.environ.get("LOCALAPPDATA", os.path.join(os.path.expanduser("~"), "AppData", "Local"))
        self.default_install_dir = os.path.join(local_appdata, "Programs", "ArcheAge Raid Timer")

        # Set window icon
        icon_candidates = [
            os.path.join(self.source_dir, "app_icon.ico"),
            os.path.join(self.source_dir, "sounds", "app_icon.png"),
        ]
        for ic in icon_candidates:
            if os.path.exists(ic):
                self.setWindowIcon(QIcon(ic))
                break

        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 14, 16, 14)
        main_layout.setSpacing(10)

        card = QFrame()
        card.setObjectName("card")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(16, 14, 16, 14)
        card_layout.setSpacing(10)

        # Title
        title_lbl = QLabel("⚔️ ArcheAge Chronicles Raid Timer")
        title_lbl.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        title_lbl.setStyleSheet("color: #FFD700; border: none;")
        card_layout.addWidget(title_lbl)

        # Description
        self.desc_lbl = QLabel(
            "Welcome to the Setup Wizard! This program will install the standalone "
            "Raid Timer Overlay on your computer."
        )
        self.desc_lbl.setWordWrap(True)
        self.desc_lbl.setStyleSheet("color: #94A3B8; font-size: 11px; border: none;")
        card_layout.addWidget(self.desc_lbl)

        # Destination Directory field
        dest_lbl = QLabel("Installation Folder:")
        dest_lbl.setStyleSheet("color: #CBD5E1; font-weight: bold; font-size: 10px; border: none;")
        card_layout.addWidget(dest_lbl)

        dest_row = QHBoxLayout()
        dest_row.setSpacing(6)
        self.path_edit = QLineEdit(self.default_install_dir)
        dest_row.addWidget(self.path_edit, stretch=4)

        browse_btn = QPushButton("Browse...")
        browse_btn.setFixedSize(70, 26)
        browse_btn.setStyleSheet("""
            QPushButton { background: #1E2838; color: #00E5FF; border: 1px solid #00ADB5; }
            QPushButton:hover { background: #00ADB5; color: #000; }
        """)
        browse_btn.clicked.connect(self.browse_folder)
        dest_row.addWidget(browse_btn, stretch=1)
        card_layout.addLayout(dest_row)

        # Options Checkboxes
        self.desktop_check = QCheckBox("Create Desktop Shortcut")
        self.desktop_check.setChecked(True)
        card_layout.addWidget(self.desktop_check)

        self.start_menu_check = QCheckBox("Create Start Menu Shortcut")
        self.start_menu_check.setChecked(True)
        card_layout.addWidget(self.start_menu_check)

        self.launch_check = QCheckBox("Launch Raid Timer immediately after installation")
        self.launch_check.setChecked(True)
        card_layout.addWidget(self.launch_check)

        # Progress bar (hidden during setup)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(False)
        card_layout.addWidget(self.progress_bar)

        self.status_lbl = QLabel("")
        self.status_lbl.setStyleSheet("color: #00FF88; font-size: 10px; font-weight: bold; border: none;")
        self.status_lbl.setVisible(False)
        card_layout.addWidget(self.status_lbl)

        main_layout.addWidget(card)

        # Footer Buttons
        footer = QHBoxLayout()
        creator_lbl = QLabel("Created by NoYz")
        creator_lbl.setStyleSheet("color: #00ADB5; font-size: 9px; font-weight: bold;")
        footer.addWidget(creator_lbl)

        footer.addStretch()

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setStyleSheet("background: #252F42; color: #FFF; border: 1px solid #3B4B66;")
        self.cancel_btn.clicked.connect(self.close)
        footer.addWidget(self.cancel_btn)

        self.install_btn = QPushButton("Install Now")
        self.install_btn.setStyleSheet("background: #00ADB5; color: #000; border: none;")
        self.install_btn.clicked.connect(self.start_installation)
        footer.addWidget(self.install_btn)

        main_layout.addLayout(footer)

    def browse_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Installation Folder", self.path_edit.text())
        if folder:
            self.path_edit.setText(folder)

    def start_installation(self):
        self.install_target = self.path_edit.text().strip()
        if not self.install_target:
            return

        self.install_btn.setEnabled(False)
        self.cancel_btn.setEnabled(False)
        self.path_edit.setEnabled(False)
        self.desktop_check.setEnabled(False)
        self.start_menu_check.setEnabled(False)
        self.launch_check.setEnabled(False)

        self.progress_bar.setVisible(True)
        self.status_lbl.setVisible(True)

        self.progress_bar.setValue(15)
        self.status_lbl.setText("Creating target directories...")
        QTimer.singleShot(250, self._step2)

    def _step2(self):
        os.makedirs(self.install_target, exist_ok=True)
        dest_sounds = os.path.join(self.install_target, "sounds")
        os.makedirs(dest_sounds, exist_ok=True)

        self.progress_bar.setValue(35)
        self.status_lbl.setText("Copying program executables & assets...")
        QTimer.singleShot(250, self._step3)

    def _step3(self):
        # 1. Copy Executable: Look in dist/ or source_dir
        exe_src = None
        for candidate in [
            os.path.join(self.source_dir, "dist", "ArcheAgeRaidTimer.exe"),
            os.path.join(self.source_dir, "ArcheAgeRaidTimer.exe")
        ]:
            if os.path.exists(candidate):
                exe_src = candidate
                break

        if exe_src:
            shutil.copy2(exe_src, os.path.join(self.install_target, "ArcheAgeRaidTimer.exe"))

        # 2. Copy Uninstaller Executable
        uninst_src = None
        for candidate in [
            os.path.join(self.source_dir, "dist", "Uninstall.exe"),
            os.path.join(self.source_dir, "Uninstall.exe")
        ]:
            if os.path.exists(candidate):
                uninst_src = candidate
                break

        if uninst_src:
            shutil.copy2(uninst_src, os.path.join(self.install_target, "Uninstall.exe"))

        # 3. Copy sounds directory
        src_sounds = os.path.join(self.source_dir, "sounds")
        dest_sounds = os.path.join(self.install_target, "sounds")
        if os.path.exists(src_sounds):
            for f in os.listdir(src_sounds):
                sp = os.path.join(src_sounds, f)
                dp = os.path.join(dest_sounds, f)
                if os.path.isfile(sp):
                    shutil.copy2(sp, dp)

        # 4. Copy app_icon.ico to install target
        ico_src = os.path.join(self.source_dir, "app_icon.ico")
        if os.path.exists(ico_src):
            shutil.copy2(ico_src, os.path.join(self.install_target, "app_icon.ico"))

        self.progress_bar.setValue(60)
        self.status_lbl.setText("Creating clean configuration...")
        QTimer.singleShot(250, self._step4)

    def _step4(self):
        # 4. Create fresh, clean config.json as requested!
        fresh_config = {
            "overlay_pos": {"x": 80, "y": 80},
            "sound_enabled": True,
            "alert_minutes": 5,
            "sound_file": "viking_horn.wav",
            "volume": 50,
            "hotkey": "F8"
        }
        config_path = os.path.join(self.install_target, "config.json")
        try:
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(fresh_config, f, indent=4)
        except Exception:
            pass

        self.progress_bar.setValue(80)
        self.status_lbl.setText("Creating shortcuts...")
        QTimer.singleShot(250, self._step5)

    def _step5(self):
        app_exe = os.path.join(self.install_target, "ArcheAgeRaidTimer.exe")
        uninst_exe = os.path.join(self.install_target, "Uninstall.exe")
        ico_path = os.path.join(self.install_target, "app_icon.ico")

        # 1. Desktop Shortcut
        if self.desktop_check.isChecked():
            desktop_lnk = os.path.join(os.path.expanduser("~"), "Desktop", "ArcheAge Raid Timer.lnk")
            self._create_shortcut(app_exe, desktop_lnk, "ArcheAge Chronicles Raid Timer Overlay", ico_path)

        # 2. Start Menu Shortcuts
        if self.start_menu_check.isChecked():
            start_menu_folder = os.path.join(
                os.environ.get("APPDATA", ""),
                "Microsoft", "Windows", "Start Menu", "Programs", "ArcheAge Raid Timer"
            )
            os.makedirs(start_menu_folder, exist_ok=True)
            app_lnk = os.path.join(start_menu_folder, "ArcheAge Raid Timer.lnk")
            uninst_lnk = os.path.join(start_menu_folder, "Uninstall Raid Timer.lnk")

            self._create_shortcut(app_exe, app_lnk, "ArcheAge Chronicles Raid Timer Overlay", ico_path)
            if os.path.exists(uninst_exe):
                self._create_shortcut(uninst_exe, uninst_lnk, "Uninstall ArcheAge Chronicles Raid Timer", ico_path)

        self.progress_bar.setValue(100)
        self.status_lbl.setText("Installation completed successfully!")

        self.desc_lbl.setText("ArcheAge Chronicles Raid Timer has been installed and is ready to use!")
        self.install_btn.setVisible(False)
        self.cancel_btn.setText("Finish")
        self.cancel_btn.setEnabled(True)
        self.cancel_btn.setStyleSheet("background: #00ADB5; color: #000; border: none;")
        self.cancel_btn.clicked.connect(self._finish_and_launch)

    def _create_shortcut(self, target_exe, link_path, description="", icon_location=""):
        cmd = f"$s=(New-Object -COM WScript.Shell).CreateShortcut('{link_path}');$s.TargetPath='{target_exe}';$s.Description='{description}';$s.WorkingDirectory='{os.path.dirname(target_exe)}';"
        if icon_location and os.path.exists(icon_location):
            cmd += f"$s.IconLocation='{icon_location},0';"
        cmd += "$s.Save()"
        try:
            subprocess.run(["powershell", "-NoProfile", "-Command", cmd], check=False, creationflags=0x08000000)
        except Exception:
            pass

    def _finish_and_launch(self):
        if self.launch_check.isChecked():
            app_exe = os.path.join(self.install_target, "ArcheAgeRaidTimer.exe")
            if os.path.exists(app_exe):
                try:
                    subprocess.Popen([app_exe], cwd=self.install_target, creationflags=0x08000000)
                except Exception:
                    pass
        self.close()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    wizard = InstallerWizard()
    wizard.show()
    sys.exit(app.exec())
