$ErrorActionPreference = "Stop"

$RepoUrl = "https://github.com/alyconr/Rapid-OS.git"
$InstallDir = Join-Path $HOME ".rapid-os"

Write-Host "🚀 Installing Rapid OS v3.0.0 for Windows..." -ForegroundColor Cyan

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Write-Error "Git is not installed. Please install Git first."
}
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Error "Python is not installed. Please install Python 3.10+ first."
}

if (Test-Path (Join-Path $InstallDir ".git")) {
    Write-Host "🔄 Updating existing Rapid OS installation in $InstallDir..."
    git -C $InstallDir pull --ff-only origin main
} elseif (Test-Path $InstallDir) {
    Write-Error "$InstallDir already exists and is not a Git repository. Remove or rename it, or install via 'pip install .'."
} else {
    Write-Host "⬇️ Cloning Rapid OS repository..."
    git clone $RepoUrl $InstallDir
}

$ProfilePath = $PROFILE
$ProfileDir = Split-Path -Parent $ProfilePath
if ($ProfileDir -and -not (Test-Path $ProfileDir)) {
    New-Item -ItemType Directory -Path $ProfileDir -Force | Out-Null
}
if (-not (Test-Path $ProfilePath)) {
    New-Item -ItemType File -Path $ProfilePath -Force | Out-Null
}

$AliasCommand = "function rapid { python `"$InstallDir\rapid.py`" `$args }"

if (-not (Select-String -Path $ProfilePath -Pattern "function rapid\b" -Quiet)) {
    Add-Content -Path $ProfilePath -Value "`n# Rapid OS CLI`n$AliasCommand"
    Write-Host "✅ Alias added to your PowerShell profile ($ProfilePath)." -ForegroundColor Green
    Write-Host "👉 Restart your terminal or run '. `"$ProfilePath`"' to start using 'rapid'."
} else {
    Write-Host "✅ Rapid OS v3.0.0 is ready." -ForegroundColor Green
}