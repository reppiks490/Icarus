#!/usr/bin/env bash
# Grok (xAI) — 2026-09-20. Whole file.
# Unix twin of start-engine-background.ps1. Only a live GET /healthz counts as
# "already running". Pid under run/. Timeout kills the child (no orphan).
# For the full plant: icarus-plant start --assets NQ
set -euo pipefail

PORT="${PORT:-8791}"
ASSETS="${ASSETS:-NQ}"
PRESET="${PRESET:-NQ-20m-ultracoded}"
ROOT="$(cd "$(dirname "$0")" && pwd)"
mkdir -p "$ROOT/run" "$ROOT/logs"
PIDFILE="${PIDFILE:-$ROOT/run/engine-background.pid}"
LOG="$ROOT/logs/engine-background.log"
HEALTH="http://127.0.0.1:${PORT}/healthz"

live() {
  curl -sf --max-time 2 "$HEALTH" >/dev/null 2>&1
}

if [[ -f "$PIDFILE" ]]; then
  if live; then
    echo "engine already live on :$PORT (healthz ok)"
    exit 0
  fi
  echo "stale pid file — no live /healthz; replacing"
  rm -f "$PIDFILE"
fi

PY="$(command -v python3 || command -v python || true)"
if [[ -z "$PY" ]]; then
  echo "Python not on PATH (need python3 or python)" >&2
  exit 1
fi

cd "$ROOT"
nohup "$PY" -m icarus_engine.cli run --assets "$ASSETS" --preset "$PRESET" --port "$PORT" \
  >>"$LOG" 2>&1 &
echo $! > "$PIDFILE"
child="$(cat "$PIDFILE")"

for _ in $(seq 1 30); do
  if live; then
    echo "engine live on http://127.0.0.1:${PORT}/  pid=$child"
    exit 0
  fi
  sleep 1
done

echo "started pid $child but /healthz did not answer within 30s — killing orphan" >&2
kill "$child" 2>/dev/null || true
rm -f "$PIDFILE"
exit 1
