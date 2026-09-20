# Grok (xAI) — 2026-09-20. Whole file.
# Start the Icarus engine dashboard in the background (Windows).
# A stale cmd.exe wrapper must not block a replacement: only a live
# GET /healthz counts as "already running". Otherwise the pid file is dropped.

param(
    [int]$Port = 8791,
    [string]$Assets = "NQ",
    [string]$Preset = "NQ-20m-ultracoded",
    [string]$PidFile = $(Join-Path $PSScriptRoot "icarus_engine.pid")
)

$pidFile = $PidFile
$health = "http://127.0.0.1:$Port/healthz"

function Test-LiveHealth {
    try {
        $r = Invoke-WebRequest -Uri $health -UseBasicParsing -TimeoutSec 2
        return $r.StatusCode -eq 200
    } catch {
        return $false
    }
}

if (Test-Path $pidFile) {
    if (Test-LiveHealth) {
        Write-Host "engine already live on :$Port (healthz ok)"
        exit 0
    }
    Write-Host "stale pid file — no live /healthz; replacing"
    Remove-Item $pidFile -ErrorAction SilentlyContinue
}

$py = Get-Command py -ErrorAction SilentlyContinue
if (-not $py) { $py = Get-Command python -ErrorAction SilentlyContinue }
if (-not $py) {
    Write-Error "Python not on PATH (need py or python)"
    exit 1
}

$proc = Start-Process -FilePath $py.Source -ArgumentList @(
    "-3", "-m", "icarus_engine.cli", "run",
    "--assets", $Assets,
    "--preset", $Preset,
    "--port", "$Port"
) -WorkingDirectory $PSScriptRoot -PassThru -WindowStyle Hidden

$proc.Id | Set-Content -Path $pidFile -Encoding ascii

$deadline = (Get-Date).AddSeconds(30)
while ((Get-Date) -lt $deadline) {
    if (Test-LiveHealth) {
        Write-Host "engine live on http://127.0.0.1:$Port/  pid=$($proc.Id)"
        exit 0
    }
    Start-Sleep -Seconds 1
}

Write-Warning "started pid $($proc.Id) but /healthz did not answer within 30s"
exit 1
