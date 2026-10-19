$ErrorActionPreference = "Stop"

$RepoUrl = "https://github.com/alyconr/Rapid-OS.git"
$RapidVersion = "v3.1.1"
$InstallDir = Join-Path $HOME ".rapid-os"
$VenvDir = Join-Path $InstallDir ".venv"
$BinDir = Join-Path $InstallDir "bin"

function Assert-LastExit([string]$What) {
    if ($LASTEXITCODE -ne 0) {
        Write-Error "$What failed (exit code $LASTEXITCODE)."
    }
}

Write-Host "🚀 Installing Rapid OS $RapidVersion (stable release) for Windows..." -ForegroundColor Cyan

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Write-Error "Git is not installed. Please install Git first."
}
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Error "Python is not installed. Please install Python 3.10+ first."
}
python -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)"
if ($LASTEXITCODE -ne 0) {
    Write-Error "Rapid OS needs Python 3.10 or newer (found: $(python --version 2>&1))."
}

if (Test-Path (Join-Path $InstallDir ".git")) {
    Write-Host "🔄 Fetching tags and checking out Rapid OS $RapidVersion in $InstallDir..."
    git -C $InstallDir fetch --tags --force origin; Assert-LastExit "git fetch"
    git -C $InstallDir checkout --detach $RapidVersion; Assert-LastExit "git checkout $RapidVersion"
} elseif (Test-Path $InstallDir) {
    Write-Error "$InstallDir already exists and is not a Git repository. Remove or rename it, or install via 'pip install .'."
} else {
    Write-Host "⬇️ Cloning Rapid OS repository and checking out $RapidVersion..."
    git clone $RepoUrl $InstallDir; Assert-LastExit "git clone"
    git -C $InstallDir fetch --tags --force origin; Assert-LastExit "git fetch"
    git -C $InstallDir checkout --detach $RapidVersion; Assert-LastExit "git checkout $RapidVersion"
}

# Keep the private environment and the launcher folder out of `git status` in the checkout.
$ExcludeFile = Join-Path $InstallDir ".git\info\exclude"
foreach ($Entry in @(".venv/", "bin/")) {
    if (-not ((Test-Path $ExcludeFile) -and (Select-String -Path $ExcludeFile -SimpleMatch -Pattern $Entry -Quiet))) {
        Add-Content -Path $ExcludeFile -Value $Entry
    }
}

# A real rapid.exe on the user PATH, not a PowerShell function: coding harnesses (Claude Code runs
# commands in Git Bash on Windows) and their hooks cannot see functions from a PowerShell profile.
$VenvPython = Join-Path $VenvDir "Scripts\python.exe"
if (-not (Test-Path $VenvPython)) {
    Write-Host "📦 Creating a private Python environment in $VenvDir..."
    python -m venv $VenvDir; Assert-LastExit "python -m venv"
}

Write-Host "📦 Installing the rapid command..."
& $VenvPython -m pip install --quiet --disable-pip-version-check -e $InstallDir; Assert-LastExit "pip install"

New-Item -ItemType Directory -Path $BinDir -Force | Out-Null
# pip's rapid.exe launcher embeds the path to the environment's python.exe, so a copy runs from
# any folder. Only rapid.exe goes on PATH: the environment's own python.exe never shadows yours.
Copy-Item -Path (Join-Path $VenvDir "Scripts\rapid.exe") -Destination (Join-Path $BinDir "rapid.exe") -Force

$UserPath = [Environment]::GetEnvironmentVariable("Path", "User")
$PathEntries = @()
if ($UserPath) { $PathEntries = $UserPath.Split(";") | Where-Object { $_ } }
if ($PathEntries -notcontains $BinDir) {
    [Environment]::SetEnvironmentVariable("Path", (($PathEntries + $BinDir) -join ";"), "User")
    Write-Host "✅ Added $BinDir to your user PATH." -ForegroundColor Green
}
if (($env:Path.Split(";")) -notcontains $BinDir) {
    $env:Path = "$env:Path;$BinDir"
}

# Installers before v3.1.1 added a 'rapid' function to the PowerShell profile; it would shadow
# rapid.exe in PowerShell, so remove it (with a backup).
$ProfilePath = $PROFILE
if ($ProfilePath -and (Test-Path $ProfilePath) -and (Select-String -Path $ProfilePath -Pattern "^function rapid\b" -Quiet)) {
    Copy-Item -Path $ProfilePath -Destination "$ProfilePath.rapid-os.bak" -Force
    $Kept = Get-Content -Path $ProfilePath | Where-Object { $_ -notmatch "^function rapid\b" -and $_ -ne "# Rapid OS CLI" }
    Set-Content -Path $ProfilePath -Value $Kept
    Write-Host "🧹 Removed the old 'rapid' function from $ProfilePath (backup: $ProfilePath.rapid-os.bak)."
}

$Installed = & (Join-Path $BinDir "rapid.exe") --version; Assert-LastExit "rapid --version"
Write-Host "✅ $Installed installed at $BinDir\rapid.exe" -ForegroundColor Green
Write-Host "👉 Open a new terminal before using 'rapid'. Launch your coding agent (claude, codex, cursor...) from a terminal where 'rapid --version' works."
