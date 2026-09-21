# Grok (xAI) — 2026-09-20. Whole file.
# Windows one-shot: install package, init drop inbox, open Explorer, start FileFeed-offline.
# Double-click start-plant.bat  OR  in PowerShell:  .\start-plant.ps1
# Leave this window open. Closing it stops the plant.
# Not a CME feed. Not TradingView scrape. You drop a Supercharts CSV you already own.
# CRITICAL: only the `py` launcher accepts -3. python.exe does not.

$ErrorActionPreference = "Continue"
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

$script:PyExe = $pyCmd.Source
$script:UsePyLauncher = ($pyCmd.Name -like "py*")

function Invoke-IcarusPython {
    param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Rest)
    if ($script:UsePyLauncher) {
        & $script:PyExe -3 @Rest
    } else {
        & $script:PyExe @Rest
    }
    return $LASTEXITCODE
}

Write-Host "Python: $($script:PyExe)  (py launcher: $($script:UsePyLauncher))"
Write-Host "installing Icarus into this Python (once, then fast)..."
$code = Invoke-IcarusPython -m pip install -e .
if ($code -ne 0) {
    Write-Host "pip install failed. Copy the error above."
    Read-Host "Press Enter to close"
    exit 1
}

Invoke-IcarusPython -m icarus_plant setup --open | Out-Host

$drop = Join-Path $PSScriptRoot "history\drop"
$hist1 = Join-Path $PSScriptRoot "history\NQ_1m.csv"
$downloads = Join-Path $env:USERPROFILE "Downloads"
if (-not (Test-Path $hist1)) {
    Write-Host ""
    Write-Host "Waiting for a Supercharts CSV."
    Write-Host "  Inbox:     $drop"
    Write-Host "  Downloads: $downloads  (the plant also pulls chart CSVs from here)"
    Write-Host ""
    Write-Host "TradingView: NQ1!  →  1 minute  →  Download chart data"
    Write-Host "Essential is enough. You do not need Plus/Premium for that button."
    Write-Host ""
    Read-Host "Press Enter AFTER the CSV is downloaded (or in history\drop\) — or Enter to start anyway"
}

Write-Host ""
Write-Host "Starting plant  --assets NQ --offline"
Write-Host "Dashboard on THIS PC:  http://127.0.0.1:8791/   token: icarus"
Write-Host "Leave this window open.  Ctrl+C to stop."
Write-Host ""

$code = Invoke-IcarusPython -m icarus_plant start --assets NQ --offline
exit $code
