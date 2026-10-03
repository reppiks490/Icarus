# Grok (xAI) — 2026-09-20. Whole file.
# Yahoo FileFeed-off plant: Brain B on NQ=F. No CSV. No --offline.
# Double-click start-yahoo.bat. Leave the window open.

$ErrorActionPreference = 'Continue'
Set-Location -LiteralPath $PSScriptRoot

Write-Host ''
Write-Host 'ICARUS plant  (Grok/xAI)  Brain B - Yahoo NQ=F'
Write-Host ('folder: ' + $PSScriptRoot)
Write-Host 'Not CME. Not NQ1!. Delayed. RTH 20m. Not a scalper.'
Write-Host ''

$pyCmd = Get-Command py -ErrorAction SilentlyContinue
if (-not $pyCmd) { $pyCmd = Get-Command python -ErrorAction SilentlyContinue }
if (-not $pyCmd) {
    Write-Host 'Python is not installed or not on PATH.'
    Read-Host 'Press Enter to close'
    exit 1
}

$PyExe = $pyCmd.Source
$UsePyLauncher = $false
if ($pyCmd.Name -eq 'py.exe' -or $pyCmd.Name -eq 'py') { $UsePyLauncher = $true }

Write-Host ('Python: ' + $PyExe)
Write-Host 'Fast startup: use the existing editable Git install; only install if ICARUS is missing.'
if ($UsePyLauncher) {
    & $PyExe -3 -c "import icarus_engine, icarus_plant" 2>$null
} else {
    & $PyExe -c "import icarus_engine, icarus_plant" 2>$null
}
if ($LASTEXITCODE -ne 0) {
    Write-Host 'ICARUS import missing. Performing one-time editable install.'
    if ($UsePyLauncher) { & $PyExe -3 -m pip install -e . } else { & $PyExe -m pip install -e . }
    if ($LASTEXITCODE -ne 0) {
        Write-Host 'pip install failed.'
        Read-Host 'Press Enter to close'
        exit 1
    }
}

$Assets = if ($env:ICARUS_ASSETS) { $env:ICARUS_ASSETS } else { 'NQ,BTC,MNQ,MES,ES,YM,MYM,RTY,M2K,GC,MGC,SI,SIL,PL,PA,MBT' }
Write-Host ('Starting plant  --assets ' + $Assets + '   (Yahoo/Coinbase, no --offline)')
Write-Host 'Dashboard on THIS PC:  http://127.0.0.1:8791/   token: icarus'
Write-Host 'Leave this window open.  Ctrl+C to stop.'
Write-Host ''

if ($UsePyLauncher) {
    & $PyExe -3 -m icarus_plant start --assets $Assets
} else {
    & $PyExe -m icarus_plant start --assets $Assets
}
exit $LASTEXITCODE
