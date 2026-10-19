param(
    [string]$StateRoot = $(if ($env:ICARUS_HOME) { $env:ICARUS_HOME } else { Split-Path $PSScriptRoot -Parent }),
    [int]$Port = 8791,
    [switch]$KeepSelection
)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath (Split-Path $PSScriptRoot -Parent)
$prefix = @()
if (Test-Path '.venv\Scripts\python.exe') { $pythonExe = (Resolve-Path '.venv\Scripts\python.exe').Path }
elseif (Get-Command python -ErrorAction SilentlyContinue) { $pythonExe = (Get-Command python).Source }
elseif (Get-Command py -ErrorAction SilentlyContinue) { $pythonExe = (Get-Command py).Source; $prefix = @('-3') }
else { throw 'Python 3.10+ is required.' }
$options = @('-m', 'icarus_engine.workspace_tools', 'restart', '--root', $StateRoot, '--port', "$Port")
if ($KeepSelection) { $options += '--keep-selection' }
& $pythonExe @prefix @options
exit $LASTEXITCODE
