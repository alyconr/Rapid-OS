$ErrorActionPreference = "Stop"
# REEMPLAZA CON TU REPO REAL:
$RepoUrl = "https://github.com/alyconr/Rapid-OS.git"
$InstallDir = "$HOME\.rapid-os"

Write-Host "🚀 Installing Rapid OS for Windows..." -ForegroundColor Cyan

# Comprobar dependencias
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Write-Error "Git is not installed."
}
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Error "Python is not installed."
}

# Clonar o Actualizar
if (Test-Path $InstallDir) {
    Write-Host "🔄 Updating..."
    git -C $InstallDir pull origin main
} else {
    Write-Host "⬇️ Cloning..."
    git clone $RepoUrl $InstallDir
}

# Crear Alias Persistente en PowerShell
$ProfilePath = $PROFILE
if (-not (Test-Path $ProfilePath)) {
    New-Item -Type File -Path $ProfilePath -Force | Out-Null
}

# Función wrapper para llamar a python
$AliasCommand = "function rapid { python `"$InstallDir\rapid.py`" `$args }"

if (-not (Select-String -Path $ProfilePath -Pattern "function rapid")) {
    Add-Content -Path $ProfilePath -Value "`n# Rapid OS CLI`n$AliasCommand"
    Write-Host "✅ Alias added to your PowerShell profile." -ForegroundColor Green
    Write-Host "👉 Please restart your terminal or run '. $ProfilePath' to start using 'rapid'."
} else {
    Write-Host "✅ Rapid OS is ready." -ForegroundColor Green
}