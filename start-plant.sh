#!/usr/bin/env bash
# Grok (xAI) — 2026-09-20. Whole file. Unix twin of start-plant.ps1.
# Not a CME feed. Drop a Supercharts CSV you already own into history/drop/.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

PY="$(command -v python3 || command -v python || true)"
if [[ -z "$PY" ]]; then
  echo "Python not on PATH (need python3 or python)" >&2
  exit 1
fi

echo "ICARUS plant  (Grok/xAI)  $ROOT"
"$PY" -m pip install -e . -q
"$PY" -m icarus_plant setup --open || true

DROP="$ROOT/history/drop"
if [[ ! -f "$ROOT/history/NQ_1m.csv" ]]; then
  echo
  echo "Copy a 1-minute NQ1! Supercharts CSV into:"
  echo "  $DROP"
  echo "Essential is enough for Download chart data."
  echo
  read -r -p "Press Enter after the CSV is in that folder (or Enter to start anyway) " _
fi

echo
echo "Starting  icarus-plant start --assets NQ --offline"
echo "Dashboard on this machine: http://127.0.0.1:8791/  token: icarus"
echo "Ctrl+C to stop."
echo
exec "$PY" -m icarus_plant start --assets NQ --offline
