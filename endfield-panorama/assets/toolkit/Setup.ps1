param([string]$Python = 'python', [switch]$CheckOnly)
$ErrorActionPreference = 'Stop'
$runner = Join-Path $PSScriptRoot 'run_panorama.py'
$venvPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
$checkPython = $Python
if (Test-Path -LiteralPath $venvPython) { $checkPython = $venvPython }
& $checkPython $runner --check
if ($LASTEXITCODE -eq 0) { Write-Host 'Ready. No installation needed.'; exit 0 }
if ($CheckOnly) { exit 1 }
& $Python -c "import sys,struct; assert sys.version_info >= (3,12) and struct.calcsize('P') == 8, 'Use 64-bit Python 3.12 or newer (tested: 3.13.3)'"
if ($LASTEXITCODE -ne 0) { throw 'Python prerequisite check failed.' }
& $Python -m venv (Join-Path $PSScriptRoot '.venv')
if ($LASTEXITCODE -ne 0) { throw 'Could not create local Python environment.' }
& $venvPython -m ensurepip --upgrade
if ($LASTEXITCODE -ne 0) { throw 'Could not prepare pip.' }
# Upstream vgamepad setup.py can start an old MSI and has no skip-install flag.
# Package hash-verified runtime files locally instead; never execute its setup.py.
& $venvPython (Join-Path $PSScriptRoot 'install_vgamepad.py')
if ($LASTEXITCODE -ne 0) { throw 'Verified vgamepad installation failed.' }
& $venvPython -m pip install -r (Join-Path $PSScriptRoot 'requirements.txt')
if ($LASTEXITCODE -ne 0) { throw 'Dependency install failed. Check network access and Python version.' }
& $venvPython $runner --check
if ($LASTEXITCODE -ne 0) {
    Write-Host 'If driver_installed is false, install the official ViGEmBus driver and restart Windows if requested:'
    Write-Host 'https://github.com/nefarius/ViGEmBus/releases/tag/v1.22.0'
    exit 1
}
Write-Host 'Ready. Run: .\Run-Panorama.ps1 -Prepared'
