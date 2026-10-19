#!/usr/bin/env bash
# Git Bash / Linux / macOS: preserve data, restart all four views in FILE mode.
set -euo pipefail
repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_dir"
if [[ -x .venv/Scripts/python.exe ]]; then
  py_command=(.venv/Scripts/python.exe)
elif [[ -x .venv/bin/python ]]; then
  py_command=(.venv/bin/python)
elif command -v python >/dev/null 2>&1; then
  py_command=(python)
elif command -v python3 >/dev/null 2>&1; then
  py_command=(python3)
elif command -v py >/dev/null 2>&1; then
  py_command=(py -3)
else
  echo 'Python 3.10+ is required.' >&2
  exit 1
fi
exec "${py_command[@]}" -m icarus_engine.workspace_tools restart "$@"
