"""Operator launcher source/argument boundaries; no provider access."""
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/start-as-is.sh'
pytestmark = pytest.mark.skipif(os.name == 'nt' or not shutil.which('bash'), reason='POSIX shell harness; Windows operator path requires Git Bash')


def launcher(tmp_path):
    repo = tmp_path / 'source with spaces'
    (repo / 'scripts').mkdir(parents=True)
    script = repo / 'scripts/start-as-is.sh'
    shutil.copy2(SCRIPT, script)
    python = repo / '.venv/bin/python'
    python.parent.mkdir(parents=True)
    python.write_text('#!/usr/bin/env bash\nif [[ "$1" == "-c" ]]; then exit 0; fi\nprintf "%s\\n" "$PWD" "$@" > "$ICARUS_CAPTURE"\n')
    python.chmod(0o755)
    return repo, script


def test_requires_explicit_feed_and_assets(tmp_path):
    _, script = launcher(tmp_path)
    result = subprocess.run(['bash', str(script)], capture_output=True, text=True)
    assert result.returncode != 0
    assert '--feed' in result.stderr and '--assets' in result.stderr


def test_uses_checkout_venv_and_preserves_argument_boundaries(tmp_path):
    repo, script = launcher(tmp_path)
    capture = tmp_path / 'capture'
    state = str(tmp_path / 'private state')
    result = subprocess.run(['bash', str(script), '--feed', 'file', '--assets', 'NQ,ES', '--root', state, '--no-browser'],
        cwd=tmp_path, env={**os.environ, 'ICARUS_CAPTURE': str(capture)}, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    args = capture.read_text().splitlines()
    assert args[:4] == [str(repo), '-m', 'icarus_plant', 'start']
    assert '--no-downloads' in args and '--bridge' not in args
    assert args[args.index('--root') + 1] == state
    assert args[args.index('--assets') + 1] == 'NQ,ES'
    assert args[args.index('--feed') + 1] == 'file'


def test_bridge_is_not_admitted_by_paper_launcher(tmp_path):
    _, script = launcher(tmp_path)
    result = subprocess.run(['bash', str(script), '--feed', 'file', '--assets', 'NQ', '--bridge'], capture_output=True, text=True)
    assert result.returncode != 0 and 'bridge' in result.stderr.lower()


def test_occupied_port_refuses_without_mutating_state(tmp_path):
    # Use the actual checkout/interpreter for the preflight; never start a service.
    with socket.socket() as occupied:
        occupied.bind(('127.0.0.1', 0))
        occupied.listen()
        state = tmp_path / 'untouched'
        result = subprocess.run(['bash', str(SCRIPT), '--feed', 'file', '--assets', 'NQ', '--root', str(state),
                                 '--engine-port', str(occupied.getsockname()[1])],
                                env={**os.environ,'ICARUS_PYTHON':sys.executable},capture_output=True,text=True)
    assert result.returncode != 0 and 'occupied' in result.stderr.lower(), result.stdout + result.stderr
    assert not state.exists()
