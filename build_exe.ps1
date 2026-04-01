param(
    [string]$Name = "ModulizerUI"
)

$ErrorActionPreference = "Stop"

Write-Host "Installing PyInstaller..." -ForegroundColor Cyan
python -m pip install --upgrade pip pyinstaller

Write-Host "Building executable..." -ForegroundColor Cyan
python -m PyInstaller `
  --noconfirm `
  --clean `
  --onefile `
  --windowed `
  --name $Name `
  "modulizer_gui.py"

Write-Host "Done. Executable created at dist\$Name.exe" -ForegroundColor Green
