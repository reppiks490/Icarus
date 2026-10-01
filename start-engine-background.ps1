# Grok (xAI) — 2026-09-20. Whole file.
# Windows launcher. Only a live GET /healthz counts as "already running".
# Pid lives under run/. If /healthz never answers, the child is killed.
# For the full plant use start-yahoo.bat or icarus-plant start --assets NQ.

param(
    [int]$Port = 8791,
    [string]$Assets = "NQ",
    [string]$Preset = "NQ-20m-ultracoded",
    [string]$PidFile = ""
)

Set-Location -LiteralPath $PSScriptRoot
$runDir = Join-Path $PSScriptRoot "run"
$logDir = Join-Path $PSScriptRoot "logs"
New-Item -ItemType Directory -Force -Path $runDir | Out-Null
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
if (-not $PidFile) { $PidFile = Join-Path $runDir "engine-background.pid" }
$log = Join-Path $logDir "engine-background.log"
$health = "http://127.0.0.1:$Port/healthz"

function Test-LiveHealth {
    try {
        $r = Invoke-WebRequest -Uri $health -UseBasicParsing -TimeoutSec 2
        return $r.StatusCode -eq 200
    } catch {
        return $false
    }
}

if (Test-Path $PidFile) {
    if (Test-LiveHealth) {
        Write-Host "engine already live on :$Port (healthz ok)"
        exit 0
    }
    Write-Host "stale pid file — no live /healthz; replacing"
    Remove-Item $PidFile -ErrorAction SilentlyContinue
}

$py = Get-Command py -ErrorAction SilentlyContinue
if (-not $py) { $py = Get-Command python -ErrorAction SilentlyContinue }
if (-not $py) {
    Write-Error "Python not on PATH (need py or python)"
    exit 1
}

$usePyLauncher = $false
if ($py.Name -eq "py.exe" -or $py.Name -eq "py") { $usePyLauncher = $true }
$argList = @()
if ($usePyLauncher) { $argList += "-3" }
$argList += @("-m", "icarus_engine.cli", "run", "--assets", $Assets, "--preset", $Preset, "--port", "$Port")

$proc = Start-Process -FilePath $py.Source -ArgumentList $argList -WorkingDirectory $PSScriptRoot -PassThru -WindowStyle Hidden -RedirectStandardOutput $log -RedirectStandardError $log

$proc.Id | Set-Content -Path $PidFile -Encoding ascii

$deadline = (Get-Date).AddSeconds(30)
while ((Get-Date) -lt $deadline) {
    if (Test-LiveHealth) {
        Write-Host "engine live on http://127.0.0.1:$Port/  pid=$($proc.Id)"
        exit 0
    }
    Start-Sleep -Seconds 1
}

Write-Warning "started pid $($proc.Id) but /healthz did not answer within 30s — killing orphan"
try { Stop-Process -Id $proc.Id -Force -ErrorAction Stop } catch {}
Remove-Item $PidFile -ErrorAction SilentlyContinue
exit 1
