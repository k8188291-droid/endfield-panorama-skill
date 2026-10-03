param(
    [switch]$Prepared,
    [switch]$DryRun,
    [switch]$Check,
    [switch]$CaptureOnly,
    [switch]$ExternalServer,
    [string]$StitchOnly,
    [string]$Session,
    [string]$Profile,
    [int]$Width = 4096,
    [double]$Delay = 8
)
$ErrorActionPreference = 'Stop'
$runnerPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $runnerPython)) { $runnerPython = (Get-Command python).Source }
$runnerArgs = @((Join-Path $PSScriptRoot 'run_panorama.py'), '--width', "$Width", '--delay', "$Delay")
if ($Prepared) { $runnerArgs += '--prepared' }
if ($DryRun) { $runnerArgs += '--dry-run' }
if ($Check) { $runnerArgs += '--check' }
if ($CaptureOnly) { $runnerArgs += '--capture-only' }
if ($ExternalServer) { $runnerArgs += '--external-server' }
if ($StitchOnly) { $runnerArgs += @('--stitch-only', $StitchOnly) }
if ($Session) { $runnerArgs += @('--session', $Session) }
if ($Profile) { $runnerArgs += @('--profile', $Profile) }
& $runnerPython @runnerArgs
exit $LASTEXITCODE
