# Grok (xAI) — 2026-09-20. Whole file.
# Windows one-shot: install package, init drop inbox, open Explorer, start FileFeed-offline.
# Double-click start-plant.bat  OR  in PowerShell:  .\start-plant.ps1
# Leave this window open. Closing it stops the plant.
# Not a CME feed. Not TradingView scrape. You drop a Supercharts CSV you already own.

$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot

Write-Host ""
Write-Host "ICARUS plant  (Grok/xAI)  Brain B — local FileFeed"
Write-Host "folder: $PSScriptRoot"
Write-Host ""

$pyCmd = Get-Command py -ErrorAction SilentlyContinue
if (-not $pyCmd) { $pyCmd = Get-Command python -ErrorAction SilentlyContinue }
if (-not $pyCmd) {
    Write-Host "Python is not installed (or not on PATH)."
    Write-Host "1. https://www.python.org/downloads/"
    Write-Host "2. Check  Add python.exe to PATH"
    Write-Host "3. Close this window, open a NEW PowerShell, run this script again."
    Read-Host "Press Enter to close"
    exit 1
}

$py = $pyCmd.Source
Write-Host "Python: $py"
Write-Host "installing Icarus into this Python (once, then fast)..."
& $py -3 -m pip install -e . --quiet
if ($LASTEXITCODE -ne 0) {
    & $py -m pip install -e .
}
if ($LASTEXITCODE -ne 0) {
    Write-Host "pip install failed. Copy the error above."
    Read-Host "Press Enter to close"
    exit 1
}

& $py -3 -m icarus_plant setup --open
if ($LASTEXITCODE -ne 0) {
    & $py -m icarus_plant setup --open
}

$drop = Join-Path $PSScriptRoot "history\drop"
$hist1 = Join-Path $PSScriptRoot "history\NQ_1m.csv"
if (-not (Test-Path $hist1)) {
    Write-Host ""
    Write-Host "Waiting for a Supercharts CSV in:"
    Write-Host "  $drop"
    Write-Host ""
    Write-Host "TradingView: NQ1!  →  1 minute  →  Download chart data  →  copy the file here."
    Write-Host "Essential is enough. You do not need Plus/Premium for that button."
    Write-Host ""
    Read-Host "Press Enter AFTER the CSV is in that folder (or Enter now to start anyway)"
}

Write-Host ""
Write-Host "Starting plant  --assets NQ --offline"
Write-Host "Dashboard on THIS PC:  http://127.0.0.1:8791/   token: icarus"
Write-Host "Leave this window open.  Ctrl+C to stop."
Write-Host ""

& $py -3 -m icarus_plant start --assets NQ --offline
if ($LASTEXITCODE -ne 0) {
    & $py -m icarus_plant start --assets NQ --offline
}
