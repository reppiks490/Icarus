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
Write-Host 'Installing Icarus into this Python. First time is slow.'
if ($UsePyLauncher) { & $PyExe -3 -m pip install -e . } else { & $PyExe -m pip install -e . }
if ($LASTEXITCODE -ne 0) {
    Write-Host 'pip install failed.'
    Read-Host 'Press Enter to close'
    exit 1
}

Write-Host 'Starting plant  --assets NQ   (Yahoo, no --offline)'
Write-Host 'Dashboard on THIS PC:  http://127.0.0.1:8791/   token: icarus'
Write-Host 'Leave this window open.  Ctrl+C to stop.'
Write-Host ''

if ($UsePyLauncher) {
    & $PyExe -3 -m icarus_plant start --assets NQ
} else {
    & $PyExe -m icarus_plant start --assets NQ
}
exit $LASTEXITCODE
