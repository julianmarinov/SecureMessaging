# SecureMessaging Installation Script for Windows
# Requires PowerShell 5.1+ and Python 3.12+

param(
    [string]$InstallDir = "$env:USERPROFILE\SecureMessaging"
)

$ErrorActionPreference = "Stop"
$ProgressPreference = 'SilentlyContinue'

# Configuration
$RepoUrl = "https://github.com/julianmarinov/SecureMessaging.git"
$PythonMinVersion = [version]"3.12.0"

# Colors and symbols
function Write-Info { Write-Host "ℹ $args" -ForegroundColor Blue }
function Write-Success { Write-Host "✓ $args" -ForegroundColor Green }
function Write-Error { Write-Host "✗ $args" -ForegroundColor Red }
function Write-Warning { Write-Host "⚠ $args" -ForegroundColor Yellow }

# Banner
Write-Host @"

╔═══════════════════════════════════════╗
║   SecureMessaging Installer v1.0.0    ║
║   End-to-End Encrypted Messaging      ║
╚═══════════════════════════════════════╝

"@ -ForegroundColor Blue

# Check for admin (we don't want admin)
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if ($isAdmin) {
    Write-Error "Please do not run this script as Administrator"
    exit 1
}

# Check for Python
Write-Info "Checking for Python $PythonMinVersion+"
$pythonCmd = $null
$pythonCandidates = @("python3.12", "python3.13", "python3.14", "python3", "python")

foreach ($cmd in $pythonCandidates) {
    try {
        $version = & $cmd --version 2>&1 | Select-String -Pattern "Python (\d+\.\d+\.\d+)" | ForEach-Object { $_.Matches.Groups[1].Value }
        if ($version) {
            $pyVersion = [version]$version
            if ($pyVersion -ge $PythonMinVersion) {
                $pythonCmd = $cmd
                Write-Success "Found Python $version"
                break
            }
        }
    }
    catch {
        continue
    }
}

if (-not $pythonCmd) {
    Write-Error "Python $PythonMinVersion+ is required but not found"
    Write-Info "Please install Python from https://www.python.org/downloads/"
    Write-Info "Make sure to check 'Add Python to PATH' during installation"
    exit 1
}

# Check for Git
Write-Info "Checking for Git"
try {
    $null = git --version
    Write-Success "Git is installed"
}
catch {
    Write-Error "Git is required but not found"
    Write-Info "Please install Git from https://git-scm.com/download/win"
    exit 1
}

# Clone or use existing repository
if (Test-Path $InstallDir) {
    Write-Warning "Directory $InstallDir already exists"
    $continue = Read-Host "Continue with existing directory? (y/N)"
    if ($continue -ne 'y' -and $continue -ne 'Y') {
        Write-Info "Installation cancelled"
        exit 0
    }
}
else {
    Write-Info "Cloning repository to $InstallDir"
    try {
        git clone $RepoUrl $InstallDir
        Write-Success "Repository cloned"
    }
    catch {
        Write-Error "Failed to clone repository: $_"
        Write-Info "You can manually clone: git clone $RepoUrl $InstallDir"
        exit 1
    }
}

# Change to install directory
Set-Location $InstallDir

# Create virtual environment
Write-Info "Creating virtual environment"
if (Test-Path ".venv") {
    Write-Warning "Virtual environment already exists, skipping creation"
}
else {
    & $pythonCmd -m venv .venv
    Write-Success "Virtual environment created"
}

# Activate virtual environment
Write-Info "Activating virtual environment"
$venvPython = Join-Path $InstallDir ".venv\Scripts\python.exe"
$venvPip = Join-Path $InstallDir ".venv\Scripts\pip.exe"

# Upgrade pip
Write-Info "Upgrading pip"
& $venvPip install --upgrade pip wheel setuptools | Out-Null

# Install dependencies
Write-Info "Installing dependencies (this may take a minute)"
& $venvPip install -r requirements.txt | Out-Null
Write-Success "Dependencies installed"

# Setup configuration
Write-Info "Setting up configuration"
if (-not (Test-Path "config\server_config.json")) {
    Copy-Item "config\server_config.example.json" "config\server_config.json"
    Write-Success "Created server_config.json from example"
}
else {
    Write-Warning "config\server_config.json already exists, skipping"
}

# Initialize database
Write-Info "Initializing database"
if (Test-Path "data\server\server.db") {
    Write-Warning "Database already exists"
    $reinit = Read-Host "Reinitialize database? (y/N)"
    if ($reinit -eq 'y' -or $reinit -eq 'Y') {
        Remove-Item "data\server\server.db" -Force
        & $venvPython scripts\init_db.py
        Write-Success "Database reinitialized"
    }
    else {
        Write-Info "Keeping existing database"
    }
}
else {
    & $venvPython scripts\init_db.py
    Write-Success "Database initialized"
}

# Create first user
$createUser = Read-Host "Would you like to create a user now? (Y/n)"
if ($createUser -ne 'n' -and $createUser -ne 'N') {
    $username = Read-Host "Enter username"
    if ($username) {
        & $venvPython scripts\create_user.py $username
        Write-Success "User created"
    }
}

# Create launcher batch files
Write-Info "Creating launcher scripts"

# Server launcher
@"
@echo off
cd /d "%~dp0"
call .venv\Scripts\activate.bat
python server\server.py %*
"@ | Out-File -FilePath "securemsg-server.bat" -Encoding ASCII

# Client launcher
@"
@echo off
cd /d "%~dp0"
call .venv\Scripts\activate.bat
python client\main.py %*
"@ | Out-File -FilePath "securemsg.bat" -Encoding ASCII

Write-Success "Created launchers: securemsg-server.bat and securemsg.bat"

# Add to PATH
$currentPath = [Environment]::GetEnvironmentVariable("Path", "User")
if ($currentPath -notlike "*$InstallDir*") {
    Write-Info "Would you like to add SecureMessaging to your PATH?"
    Write-Info "This will allow you to run 'securemsg' and 'securemsg-server' from anywhere"
    $addPath = Read-Host "Add to PATH? (y/N)"

    if ($addPath -eq 'y' -or $addPath -eq 'Y') {
        [Environment]::SetEnvironmentVariable("Path", "$currentPath;$InstallDir", "User")
        Write-Success "Added to PATH"
        Write-Info "You may need to restart your terminal for changes to take effect"
    }
}

# Print final instructions
Write-Host @"

═══════════════════════════════════════════════════════════
Installation Complete!
═══════════════════════════════════════════════════════════

Installation directory: $InstallDir

To start the server:
  cd $InstallDir
  .\securemsg-server.bat

To start the client:
  cd $InstallDir
  .\securemsg.bat

To create additional users:
  cd $InstallDir
  .venv\Scripts\activate
  python scripts\create_user.py <username>

Configuration file: config\server_config.json

Documentation: $InstallDir\README.md
Visit: https://github.com/julianmarinov/SecureMessaging

"@ -ForegroundColor Green
