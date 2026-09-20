#!/usr/bin/env bash
# Grok (xAI) — 2026-09-20. Whole file.
# Unix twin of start-engine-background.ps1. Only a live GET /healthz counts as
# "already running". A stale pid file is dropped (Remove-Item $pidFile).
# For the full plant (drop inbox, FileFeed-offline, restart-on-crash) use
#   icarus-plant start --assets NQ --offline
# instead of this launcher.
set -euo pipefail
set -euo pipefail

PORT="${PORT:-8791}"
ASSETS="${ASSETS:-NQ}"
PRESET="${PRESET:-NQ-20m-ultracoded}"
ROOT="$(cd "$(dirname "$0")" && pwd)"
PIDFILE="${PIDFILE:-$ROOT/icarus_engine.pid}"
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
  >/dev/null 2>&1 &
echo $! > "$PIDFILE"

for _ in $(seq 1 30); do
  if live; then
    echo "engine live on http://127.0.0.1:${PORT}/  pid=$(cat "$PIDFILE")"
    exit 0
  fi
  sleep 1
done

echo "started pid $(cat "$PIDFILE") but /healthz did not answer within 30s" >&2
exit 1
