"""
ArcheAge Chronicles - Raid Timer Uninstaller
Clean, modern uninstallation wizard for ArcheAge Chronicles Raid Timer.

Created by NoYz
"""

import sys
import os
import shutil
import subprocess

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont, QColor, QIcon
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, 
    QLabel, QPushButton, QFrame, QCheckBox, QProgressBar
)

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

        # Determine installation directory
        if getattr(sys, 'frozen', False):
            self.install_dir = os.path.dirname(sys.executable)
        else:
            self.install_dir = os.path.dirname(os.path.abspath(__file__))

        self.desktop_lnk = os.path.join(os.path.expanduser("~"), "Desktop", "ArcheAge Raid Timer.lnk")
        self.start_menu_dir = os.path.join(
            os.environ.get("APPDATA", ""), 
            "Microsoft", "Windows", "Start Menu", "Programs", "ArcheAge Raid Timer"
        )

        # Set window icon
        icon_candidates = [
            os.path.join(self.install_dir, "app_icon.ico"),
            os.path.join(self.install_dir, "sounds", "app_icon.png"),
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
        card_layout.setContentsMargins(14, 12, 14, 12)
        card_layout.setSpacing(8)

        # Title
        title_lbl = QLabel("⚔️ Uninstall ArcheAge Chronicles Raid Timer")
        title_lbl.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        title_lbl.setStyleSheet("color: #E63946; border: none;")
        card_layout.addWidget(title_lbl)

        # Message
        self.desc_lbl = QLabel(
            "Are you sure you want to completely remove ArcheAge Chronicles Raid Timer "
            "and all its shortcuts from your computer?"
        )
        self.desc_lbl.setWordWrap(True)
        self.desc_lbl.setStyleSheet("color: #94A3B8; font-size: 11px; border: none;")
        card_layout.addWidget(self.desc_lbl)

        # Location info
        loc_lbl = QLabel(f"Location: {self.install_dir}")
        loc_lbl.setStyleSheet("color: #64748B; font-size: 9px; font-family: Consolas; border: none;")
        loc_lbl.setWordWrap(True)
        card_layout.addWidget(loc_lbl)

        # Options
        self.remove_data_check = QCheckBox("Also remove custom sounds and configuration (config.json)")
        self.remove_data_check.setChecked(True)
        card_layout.addWidget(self.remove_data_check)

        # Progress bar (initially hidden)
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

        # Footer Buttons
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
        # 1. Remove Desktop shortcut
        if os.path.exists(self.desktop_lnk):
            try: os.remove(self.desktop_lnk)
            except Exception: pass

        self.progress_bar.setValue(50)
        self.status_lbl.setText("Removing Start Menu shortcuts...")
        QTimer.singleShot(300, self._step3)

    def _step3(self):
        # 2. Remove Start Menu folder
        if os.path.exists(self.start_menu_dir):
            try: shutil.rmtree(self.start_menu_dir, ignore_errors=True)
            except Exception: pass

        self.progress_bar.setValue(80)
        self.status_lbl.setText("Cleaning program files...")
        QTimer.singleShot(300, self._step4)

    def _step4(self):
        remove_all = self.remove_data_check.isChecked()

        # Delete program files except current running uninstaller
        try:
            for item in os.listdir(self.install_dir):
                item_path = os.path.join(self.install_dir, item)
                # Don't delete running uninstaller executable directly
                if "uninstall" in item.lower():
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
        # Schedule deletion of remaining uninstaller and directory after process exits
        cmd = f'cmd.exe /c timeout /t 1 /nobreak >nul & rmdir /s /q "{self.install_dir}"'
        try:
            subprocess.Popen(cmd, shell=True, creationflags=0x08000000) # CREATE_NO_WINDOW
        except Exception:
            pass
        self.close()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    wizard = UninstallerWizard()
    wizard.show()
    sys.exit(app.exec())
