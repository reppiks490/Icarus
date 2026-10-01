# Grok (xAI) — 2026-09-20. Whole file.
# Windows one-shot. Double-click start-plant.bat  OR  .\start-plant.ps1
# Leave this window open. Closing it stops the plant.
# Not a CME feed. Not TradingView scrape.
# Only the py launcher accepts -3. Never pass -3 to python.exe.
# PowerShell 5.1: keep static strings in single quotes. Never put commas
# inside parentheses in a double-quoted Write-Host.

$ErrorActionPreference = 'Continue'
Set-Location -LiteralPath $PSScriptRoot

Write-Host ''
Write-Host 'ICARUS plant  (Grok/xAI)  Brain B - local FileFeed'
Write-Host ('folder: ' + $PSScriptRoot)
Write-Host ''

$pyCmd = Get-Command py -ErrorAction SilentlyContinue
if (-not $pyCmd) { $pyCmd = Get-Command python -ErrorAction SilentlyContinue }
if (-not $pyCmd) {
    Write-Host 'Python is not installed or not on PATH.'
    Write-Host '1. https://www.python.org/downloads/'
    Write-Host '2. Check  Add python.exe to PATH'
    Write-Host '3. Close this window, open a NEW PowerShell, run this script again.'
    Read-Host 'Press Enter to close'
    exit 1
}

$PyExe = $pyCmd.Source
$UsePyLauncher = $false
if ($pyCmd.Name -eq 'py.exe' -or $pyCmd.Name -eq 'py') { $UsePyLauncher = $true }

if ($PyExe -like '*WindowsApps\python*') {
    Write-Host 'This is the Microsoft Store python stub, not a real interpreter.'
    Write-Host 'Install from https://www.python.org/downloads/ and check  Add python.exe to PATH'
    Read-Host 'Press Enter to close'
    exit 1
}

Write-Host ('Python: ' + $PyExe)
Write-Host 'Installing Icarus into this Python. First time is slow.'

if ($UsePyLauncher) {
    & $PyExe -3 -m pip install -e .
} else {
    & $PyExe -m pip install -e .
}
if ($LASTEXITCODE -ne 0) {
    Write-Host 'pip install failed. Copy the error above.'
    Read-Host 'Press Enter to close'
    exit 1
}

if ($UsePyLauncher) {
    & $PyExe -3 -m icarus_plant setup --open
} else {
    & $PyExe -m icarus_plant setup --open
}

$drop = Join-Path $PSScriptRoot 'history\drop'
$hist1 = Join-Path $PSScriptRoot 'history\NQ_1m.csv'
$downloads = Join-Path $env:USERPROFILE 'Downloads'
if (-not (Test-Path -LiteralPath $hist1)) {
    Write-Host ''
    Write-Host 'Waiting for a Supercharts CSV.'
    Write-Host ('  Inbox:     ' + $drop)
    Write-Host ('  Downloads: ' + $downloads)
    Write-Host ''
    Write-Host 'TradingView CSV export needs Plus or higher. Essential cannot download Supercharts.'
    Write-Host 'Typical filename: CME_MINI_NQ1!, 1.csv'
    Write-Host 'No Plus: press Ctrl+C and run  start-yahoo.bat  (Yahoo NQ=F, delayed).'
    Write-Host ''
    Read-Host 'Press Enter AFTER the CSV is downloaded - or Enter to start anyway'
}

Write-Host ''
Write-Host 'Starting plant  --assets NQ --offline'
Write-Host 'Dashboard on THIS PC:  http://127.0.0.1:8791/   token: icarus'
Write-Host 'Leave this window open.  Ctrl+C to stop.'
Write-Host ''

if ($UsePyLauncher) {
    & $PyExe -3 -m icarus_plant start --assets NQ --offline
} else {
    & $PyExe -m icarus_plant start --assets NQ --offline
}
exit $LASTEXITCODE
