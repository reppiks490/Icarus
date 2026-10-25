#!/usr/bin/env bash
# Current common dashboard + existing private state. No implicit feed or asset changes.
set -euo pipefail
repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_dir"
printf 'ICARUS source revision: '
git rev-parse --short=12 HEAD 2>/dev/null || echo 'unavailable'

setup=false
arguments=()
for argument in "$@"; do
  if [[ "$argument" == '--setup' ]]; then setup=true; else arguments+=("$argument"); fi
done

# Refuse an empty main universe before installing packages or invoking plant.
# A flag alone can carry an empty shell variable and otherwise starts zero runners.
has_feed=false; has_assets=false; help=false; assets_value=''
for ((argument_index=0; argument_index<${#arguments[@]}; argument_index++)); do
  argument="${arguments[argument_index]}"
  case "$argument" in
    --feed|--feed=*) has_feed=true ;;
    --assets) has_assets=true; assets_value="${arguments[argument_index+1]:-}" ;;
    --assets=*) has_assets=true; assets_value="${argument#--assets=}" ;;
    --help|-h) help=true ;;
    --bridge) echo 'This paper launcher does not start the account bridge.' >&2; exit 1 ;;
  esac
done
if ! $help && { ! $has_feed || ! $has_assets; }; then
  echo 'Specify --feed file|yahoo|databento and --assets YOUR,MAIN,SYMBOLS explicitly. See START_HERE.md.' >&2
  exit 1
fi
if ! $help && [[ -z "${assets_value//[[:space:],]/}" || "$assets_value" == --* ]]; then
  echo 'Specify --assets with a non-empty comma-separated symbol list, for example --assets NQ,ES.' >&2
  exit 1
fi

if $setup; then
  if [[ ! -f .venv/pyvenv.cfg ]]; then
    if command -v py >/dev/null 2>&1; then bootstrap=(py -3)
    elif command -v python3 >/dev/null 2>&1; then bootstrap=(python3)
    elif command -v python >/dev/null 2>&1; then bootstrap=(python)
    else echo 'Install Python 3.11 or 3.12 (64-bit) first.' >&2; exit 1; fi
    "${bootstrap[@]}" -c 'import sys; assert sys.version_info >= (3,10), "Python 3.10+ required"'
    "${bootstrap[@]}" -m venv .venv
  fi
fi
if ! $setup && [[ -n "${ICARUS_PYTHON:-}" ]]; then python_command=("$ICARUS_PYTHON")
elif [[ -x .venv/Scripts/python.exe ]]; then python_command=(.venv/Scripts/python.exe)
elif [[ -x .venv/bin/python ]]; then python_command=(.venv/bin/python)
else echo 'Run this command again with --setup to create the checkout .venv.' >&2; exit 1; fi
if $setup; then
  # On Python 3.10/3.11 pip selects stdlib distutils. Importing setuptools
  # afterwards can assert while trying to replace that same module. Keep the
  # matching build tools in this venv and scope the workaround to setup only.
  # Python 3.12+ has no stdlib distutils and must use setuptools' local copy.
  setup_distutils="$("${python_command[@]}" -c 'import sys; print("stdlib" if sys.version_info < (3,12) else "local")')"
  SETUPTOOLS_USE_DISTUTILS="$setup_distutils" "${python_command[@]}" -m pip install --upgrade pip 'setuptools>=68' wheel
  SETUPTOOLS_USE_DISTUTILS="$setup_distutils" "${python_command[@]}" -m pip install --no-build-isolation -e '.[bridge,ml,databento]' 'cryptography>=44,<47'
fi

"${python_command[@]}" -c '
import argparse, os, socket, sys
from pathlib import Path
import icarus_engine, icarus_plant
assert sys.version_info >= (3,10), "Python 3.10+ required"
repo = Path.cwd().resolve()
for module in (icarus_engine, icarus_plant):
    if Path(module.__file__).resolve().parent.parent != repo:
        raise SystemExit("Wrong package source; run --setup in this checkout")
p = argparse.ArgumentParser(add_help=False)
p.add_argument("--root", default=os.environ.get("ICARUS_HOME") or str(repo))
p.add_argument("--engine-port", type=int, default=8791)
a, rest = p.parse_known_args(sys.argv[1:])
print("Source:", repo, "\nPython:", sys.executable, "\nPrivate state:", Path(a.root).expanduser().resolve(), flush=True)
if "--help" not in rest and "-h" not in rest:
    if not 1 <= a.engine_port <= 65535: raise SystemExit("Port must be 1..65535")
    with socket.socket() as probe:
        # Match the POSIX HTTP server: closed connections in TIME_WAIT are not
        # an active listener. Windows retains its exclusive default bind check;
        # SO_REUSEADDR there can admit a port owned by another running process.
        if os.name != "nt": probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try: probe.bind(("127.0.0.1", a.engine_port))
        except OSError: raise SystemExit("Port occupied. Stop the existing owner window with Ctrl+C, or choose --engine-port. No process was killed.")
    root = Path(a.root).expanduser().resolve()
    if not root.is_dir(): raise SystemExit("Private state root does not exist; choose the existing data directory with --root")
    print("Saved workspaces: %s/4; main journal: %s" % (sum((root/"command_centers"/(name+".json")).is_file() for name in ("cc1","cc2","cc3","cc4")), (root/"icarus_engine.db").is_file()), flush=True)
    print("Main: http://127.0.0.1:%s/" % a.engine_port, flush=True)
    for name in ("cc1", "cc2", "cc3", "cc4", "connections"):
        print("  http://127.0.0.1:%s/dashboards/%s" % (a.engine_port,name), flush=True)
' "${arguments[@]}"
exec "${python_command[@]}" -m icarus_plant start --no-downloads --token "${ICARUS_TOKEN:-icarus}" "${arguments[@]}"
