# -*- mode: python ; coding: utf-8 -*-

import os

ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))

a = Analysis(
    [os.path.join(ROOT, "app.py")],
    pathex=[ROOT],
    binaries=[],
    datas=[
        (os.path.join(ROOT, "assets", "sounds"), os.path.join("assets", "sounds")),
        (os.path.join(ROOT, "assets", "icons"), os.path.join("assets", "icons")),
        (os.path.join(ROOT, "assets", "icons", "app_icon.ico"), "."),
    ],
    hiddenimports=["PyQt6.QtSvg", "PyQt6.QtMultimedia", "PyQt6.QtTextToSpeech"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "PIL.ImageQt"],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="ChroniclesRaidTimer",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    manifest=os.path.join(SPECPATH, "app.manifest"),
    version=os.path.join(SPECPATH, "version_info.txt"),
    icon=[os.path.join(ROOT, "assets", "icons", "app_icon.ico")],
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="ChroniclesRaidTimerPayload",
)
