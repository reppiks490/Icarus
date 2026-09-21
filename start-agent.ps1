# Grok (xAI) — 2026-09-21. Whole file. Desk sidecar. Loopback only.
Set-Location -LiteralPath $PSScriptRoot
$py = Get-Command py -ErrorAction SilentlyContinue
if ($py) { & py -3 -m icarus_agent serve }
else { python -m icarus_agent serve }
