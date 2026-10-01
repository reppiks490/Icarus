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
$outLog = Join-Path $logDir "engine-background.out.log"
$errLog = Join-Path $logDir "engine-background.err.log"
$health = "http://127.0.0.1:$Port/healthz"

function Test-LiveHealth {
    try {
        $r = Invoke-WebRequest -Uri $health -UseBasicParsing -TimeoutSec 2
        return $r.StatusCode -eq 200
    } catch {
        return $false
    }
}

function Get-OwnedEngineProcess {
    if (-not (Test-Path -LiteralPath $PidFile)) { return $null }
    try {
        $pidText = (Get-Content -LiteralPath $PidFile -ErrorAction Stop | Select-Object -First 1).Trim()
        $pidValue = [int]$pidText
        $proc = Get-CimInstance Win32_Process -Filter ("ProcessId=" + $pidValue) -ErrorAction Stop
        if (-not $proc) { return $null }
        $cmd = [string]$proc.CommandLine
        if ($cmd -notmatch 'icarus_engine\.cli' -or $cmd -notmatch '\brun\b' -or $cmd -notmatch ('--port\s+["'']?' + [regex]::Escape([string]$Port) + '\b')) {
            return $null
        }
        return Get-Process -Id $pidValue -ErrorAction Stop
    } catch {
        return $null
    }
}

$owned = Get-OwnedEngineProcess
if (Test-LiveHealth) {
    if ($owned) {
        Write-Host "engine already live on :$Port (healthz ok, pid=$($owned.Id))"
        exit 0
    }
    Write-Error "engine /healthz is already live on :$Port but PID ownership is missing or invalid; refusing a duplicate launch"
    exit 1
}

if (Test-Path -LiteralPath $PidFile) {
    if ($owned) {
        Write-Error "recorded ICARUS engine pid=$($owned.Id) is still alive but /healthz is down; refusing to start a second engine"
        exit 1
    }
    Write-Host "stale pid file — recorded process is not an owned ICARUS engine; replacing"
    Remove-Item -LiteralPath $PidFile -ErrorAction SilentlyContinue
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

$proc = Start-Process -FilePath $py.Source -ArgumentList $argList -WorkingDirectory $PSScriptRoot -PassThru -WindowStyle Hidden -RedirectStandardOutput $outLog -RedirectStandardError $errLog

$proc.Id | Set-Content -Path $PidFile -Encoding ascii

$deadline = (Get-Date).AddSeconds(30)
while ((Get-Date) -lt $deadline) {
    if (Test-LiveHealth) {
        $proc.Refresh()
        if (-not $proc.HasExited) {
            Write-Host "engine live on http://127.0.0.1:$Port/  pid=$($proc.Id)"
            exit 0
        }
        Write-Error "healthz is live but the process just started by this launcher already exited; another process owns :$Port"
        Remove-Item -LiteralPath $PidFile -ErrorAction SilentlyContinue
        exit 1
    }
    if ($proc.HasExited) {
        Write-Error "engine process pid=$($proc.Id) exited before /healthz became ready; see $errLog"
        Remove-Item -LiteralPath $PidFile -ErrorAction SilentlyContinue
        exit 1
    }
    Start-Sleep -Seconds 1
}

Write-Warning "started pid $($proc.Id) but /healthz did not answer within 30s — killing orphan"
try { Stop-Process -Id $proc.Id -Force -ErrorAction Stop } catch {}
Remove-Item $PidFile -ErrorAction SilentlyContinue
exit 1
