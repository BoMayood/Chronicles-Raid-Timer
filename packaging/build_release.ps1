$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$ScratchRoot = Split-Path -Parent $Root
$InstallerOutDir = Join-Path $ScratchRoot "Chronicles_Raid_Timer_Installer"

Push-Location $Root
try {
    Write-Host "[1/5] Verifying audio & icon assets..."
    python packaging/generate_assets.py

    Write-Host "[2/5] Running full unit & UI test suite..."
    $env:PYTHONPATH = $Root
    python -m unittest discover -s tests -v

    Write-Host "[3/5] Building standalone portable EXE (upx=False)..."
    python -m PyInstaller --noconfirm --clean --distpath "$Root\dist" --workpath "$Root\build" packaging/ChroniclesRaidTimer.spec

    Write-Host "[4/5] Building fast-launch onedir payload & compressing payload.zip..."
    $PayloadDist = Join-Path $Root "build\payload_dist"
    python -m PyInstaller --noconfirm --clean --distpath "$PayloadDist" --workpath "$Root\build" packaging/ChroniclesAppPayload.spec
    $PayloadZip = Join-Path $Root "build\payload.zip"
    if (Test-Path $PayloadZip) { Remove-Item $PayloadZip -Force }
    python -c "
import os, zipfile
src = r'$PayloadDist\ChroniclesRaidTimerPayload'
out_zip = r'$PayloadZip'
with zipfile.ZipFile(out_zip, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
    for r, _, files in os.walk(src):
        for fn in files:
            full = os.path.join(r, fn)
            rel = os.path.relpath(full, src)
            zf.write(full, rel)
print('Created payload.zip:', os.path.getsize(out_zip), 'bytes')
"

    Write-Host "[5/5] Building standalone Setup Installer in isolated folder: $InstallerOutDir"
    New-Item -ItemType Directory -Force -Path $InstallerOutDir | Out-Null
    Get-ChildItem -Path $InstallerOutDir -Filter "Chronicles_Raid_Timer_Setup_*.exe" -ErrorAction SilentlyContinue | Remove-Item -Force
    python -m PyInstaller --noconfirm --clean --distpath "$InstallerOutDir" --workpath "$Root\build" packaging/ChroniclesSetup.spec

    Write-Host "Build complete!"
    Write-Host "  Portable EXE : $Root\dist\ChroniclesRaidTimer.exe"
    Write-Host "  Setup EXE    : $InstallerOutDir\Chronicles_Raid_Timer_Setup_v0.6.exe"
}
finally {
    Pop-Location
}
