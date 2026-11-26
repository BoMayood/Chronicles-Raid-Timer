# -*- mode: python ; coding: utf-8 -*-

import os

ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))

a = Analysis(
    [os.path.join(SPECPATH, "installer_wizard.py")],
    pathex=[ROOT],
    binaries=[],
    datas=[
        (os.path.join(ROOT, "build", "payload.zip"), "."),
        (os.path.join(ROOT, "assets", "icons"), os.path.join("assets", "icons")),
    ],
    hiddenimports=["PyQt6.QtSvg"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "numpy", "cv2", "PyQt6.QtMultimedia", "PyQt6.QtTextToSpeech"],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="Chronicles_Raid_Timer_Setup_v0.6",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    manifest=os.path.join(SPECPATH, "app.manifest"),
    version=os.path.join(SPECPATH, "version_info_setup.txt"),
    icon=[os.path.join(ROOT, "assets", "icons", "app_icon.ico")],
)
