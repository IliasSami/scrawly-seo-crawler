# Scrawly one-line installer for Windows (PowerShell).
#
#   irm https://raw.githubusercontent.com/IliasSami/scrawly-seo-crawler/main/install.ps1 | iex
#
# Checks for git and Python 3.11+ (installing them with winget when missing),
# downloads Scrawly into %USERPROFILE%\Scrawly (or $env:SCRAWLY_HOME), and runs
# its installer, which adds Scrawly to the Start Menu and the Desktop.
# Re-running it updates an existing install.
$ErrorActionPreference = 'Stop'

$Repo = if ($env:SCRAWLY_REPO) { $env:SCRAWLY_REPO } else { 'https://github.com/IliasSami/scrawly-seo-crawler.git' }
$Dest = if ($env:SCRAWLY_HOME) { $env:SCRAWLY_HOME } else { Join-Path $env:USERPROFILE 'Scrawly' }

function Have([string]$cmd) { [bool](Get-Command $cmd -ErrorAction SilentlyContinue) }

function Update-SessionPath {
  $env:Path = [Environment]::GetEnvironmentVariable('Path', 'Machine') + ';' +
              [Environment]::GetEnvironmentVariable('Path', 'User')
}

function Find-Python {
  # Prefer the Python launcher (py), then a python.exe on PATH. The Microsoft
  # Store "python" alias fails the version check, so it's skipped. Probes may
  # print to stderr; that must not stop the script (Windows PowerShell 5.1).
  $ErrorActionPreference = 'Continue'
  if (Have 'py') {
    foreach ($v in '3.13', '3.12', '3.11') {
      & py "-$v" -c "import sys" 2>$null
      if ($LASTEXITCODE -eq 0) { return @('py', "-$v") }
    }
  }
  if (Have 'python') {
    & python -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)" 2>$null
    if ($LASTEXITCODE -eq 0) { return @('python') }
  }
  return $null
}

function Install-WithWinget([string]$id) {
  if (-not (Have 'winget')) { return }
  Write-Host "Installing $id with winget..."
  winget install --id $id -e --source winget --accept-package-agreements --accept-source-agreements
  Update-SessionPath
}

Write-Host 'Scrawly installer'
Write-Host '================='
Write-Host "Installing into: $Dest"

if (-not (Have 'git')) { Install-WithWinget 'Git.Git' }
if (-not (Have 'git')) {
  throw "git is needed. Install it from https://git-scm.com/download/win, then run this again."
}

$py = Find-Python
if (-not $py) { Install-WithWinget 'Python.Python.3.12'; $py = Find-Python }
if (-not $py) {
  throw "Python 3.11 or newer is needed. Install it from https://www.python.org/downloads/ (tick 'Add python.exe to PATH'), then run this again."
}

if (Test-Path (Join-Path $Dest '.git')) {
  Write-Host 'Updating the existing copy...'
  git -C $Dest pull --ff-only
} elseif ((Test-Path $Dest) -and (Get-ChildItem -Force $Dest | Select-Object -First 1)) {
  throw "$Dest already exists and isn't a Scrawly folder. Choose another folder by setting SCRAWLY_HOME."
} else {
  Write-Host 'Downloading Scrawly...'
  git clone $Repo $Dest
}

Set-Location $Dest
# Show the installer's symbols correctly; Python falls back safely otherwise.
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch { }
$env:PYTHONIOENCODING = 'utf-8'
if ($py.Count -gt 1) { & $py[0] $py[1] 'scripts\install.py' } else { & $py[0] 'scripts\install.py' }
if ($LASTEXITCODE -ne 0) { throw "The Scrawly installer stopped with an error (code $LASTEXITCODE). See the messages above." }
