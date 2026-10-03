param([string]$DestinationRoot)
$ErrorActionPreference = 'Stop'
if (-not $DestinationRoot) {
    if ($env:CODEX_HOME) { $DestinationRoot = Join-Path $env:CODEX_HOME 'skills' }
    else { $DestinationRoot = Join-Path $env:USERPROFILE '.codex\skills' }
}
$skillSource = Join-Path $PSScriptRoot 'endfield-panorama'
$skillDestination = Join-Path $DestinationRoot 'endfield-panorama'
if (-not (Test-Path -LiteralPath (Join-Path $skillSource 'SKILL.md'))) { throw 'Skill package is missing.' }
if (Test-Path -LiteralPath $skillDestination) { throw "Already exists; not overwritten: $skillDestination" }
New-Item -ItemType Directory -Path $DestinationRoot -Force | Out-Null
Copy-Item -LiteralPath $skillSource -Destination $skillDestination -Recurse
Write-Host "Installed: $skillDestination"
Write-Host 'Open a new Codex conversation, then invoke $endfield-panorama.'
