"""Local paper-dashboard maintenance without deleting journals or enabling feeds.

``restart`` explicitly uses file history; it cannot arm brokers or select a paid
feed. Existing asset selection expands only through the server's flat-position
guard. Settings and ledger files are never edited directly by this tool.
"""
from __future__ import annotations

import argparse
from functools import partial
from http.client import HTTPConnection
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from .workspace_universe import dashboard_assets

IDS = ('cc1', 'cc2', 'cc3', 'cc4')


def request(port, token, path, body=None):
    connection = HTTPConnection('127.0.0.1', port, timeout=120)
    try:
        headers = {'Authorization': 'Bearer '+token}
        if body is not None: headers['Content-Type'] = 'application/json'
        connection.request('GET' if body is None else 'POST', path,
                           None if body is None else json.dumps(body, allow_nan=False), headers)
        response = connection.getresponse()
        raw = response.read(8*1024*1024+1)
        if len(raw) > 8*1024*1024: raise RuntimeError('Response exceeded maintenance limit')
        data = json.loads(raw)
        if not isinstance(data, dict): raise RuntimeError('Invalid maintenance response')
        if response.status >= 400:
            raise RuntimeError(f'HTTP {response.status}: {data.get("detail", "request refused")}')
        return data
    finally:
        connection.close()


def expand(fetch, profiles):
    """Preserve inputs/chart/journals; require file mode and verified readback."""
    if not profiles or any(key not in IDS for key in profiles) or len(set(profiles)) != len(profiles):
        raise ValueError('Select distinct CC1–CC4 profiles')
    desired = dashboard_assets()
    states = {}
    # Validate every selected identity/capability before the first write.
    for key in profiles:
        state = fetch('/api/command-centers/'+key)
        own = state.get('profile', {})
        selectable = {row.get('symbol') for row in state.get('available_assets', [])
                      if row.get('selectable') is True}
        if (state.get('mode') != 'concurrent_paper' or state.get('execution_authorized') is not False
                or state.get('runtime_feed_mode') != 'file' or own.get('id') != key
                or own.get('runtime_available') is not True or not set(desired) <= selectable):
            raise RuntimeError(key+': expansion requires an observed file-mode paper runtime and all canonical assets')
        states[key] = own
    result = {}
    for key in profiles:
        if set(states[key].get('assets', [])) >= set(desired):
            result[key] = 'ALREADY_COMPLETE'; continue
        # Preserve any existing extra selected identity; no chart/input overrides.
        assets = list(dict.fromkeys([*states[key].get('assets', []), *desired]))
        answer = fetch('/admin/command-centers/'+key, {'assets':assets})
        if answer.get('ok') is not True: raise RuntimeError(key+': asset update was refused')
        verified = fetch('/api/command-centers/'+key).get('profile', {})
        if verified.get('id') != key or set(verified.get('assets', [])) != set(assets):
            raise RuntimeError(key+': asset update readback differs; inspect this workspace')
        result[key] = 'EXPANDED'
    return result


def restart(args):
    root = str(Path(args.root).expanduser().resolve())
    command = [sys.executable, '-m', 'icarus_plant']
    subprocess.run([*command, 'stop', '--root', root], check=True)
    # Do not claim an unowned process which happens to answer on this port.
    try:
        connection = HTTPConnection('127.0.0.1', args.port, timeout=2)
        connection.request('GET', '/healthz')
        response = connection.getresponse()
        response.read(1024)
    except OSError:
        pass
    else:
        raise RuntimeError('Port is still occupied. Stop its owning engine window before restarting.')
    finally:
        connection.close()
    environment = dict(os.environ, ICARUS_HOME=root, ICARUS_FEED='file')
    child = subprocess.Popen([*command, 'start', '--root', root, '--offline', '--feed', 'file',
                              '--assets', ','.join(dashboard_assets()), '--engine-port', str(args.port),
                              '--token', args.token, '--no-downloads', '--no-browser'], env=environment)
    fetch = partial(request, args.port, args.token)
    try:
        deadline = time.monotonic()+90
        while time.monotonic() < deadline:
            if child.poll() is not None: raise RuntimeError('Plant exited before dashboard startup')
            try:
                fetch('/api/command-centers/cc1'); break
            except (OSError, RuntimeError, ValueError): time.sleep(1)
        else: raise RuntimeError('Dashboard did not become ready within 90 seconds')
        if not args.keep_selection:
            try:
                print(json.dumps(expand(fetch, IDS), indent=2), flush=True)
            except (RuntimeError, OSError, ValueError) as error:
                print('Universe selection incomplete: '+str(error)+
                      '\nExisting ledgers/settings preserved. Open positions may require a deliberate flatten before applying assets.',
                      file=sys.stderr, flush=True)
        print('\nFour paper dashboards (leave this window open):', flush=True)
        for key in IDS: print(f'  http://127.0.0.1:{args.port}/dashboards/{key}', flush=True)
        print(f'Connections: http://127.0.0.1:{args.port}/connections\nFeed: local files only. No new market data is acquired.', flush=True)
        return child.wait()
    finally:
        if child.poll() is None:
            # Reap our own POSIX supervisor directly. Running the external stop
            # command first would mistake its unreaped zombie for a survivor.
            if os.name != 'nt': child.terminate()
            else: subprocess.run([*command, 'stop', '--root', root], check=False)
            try: child.wait(timeout=15)
            except subprocess.TimeoutExpired:
                subprocess.run([*command, 'stop', '--root', root], check=False)
                child.wait(timeout=15)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('restart', 'status', 'expand', 'controls'))
    parser.add_argument('--port', type=int, default=8791)
    parser.add_argument('--root', default=os.environ.get('ICARUS_HOME') or os.getcwd())
    parser.add_argument('--token', default=os.environ.get('ICARUS_TOKEN') or 'icarus')
    parser.add_argument('--workspace', choices=(*IDS, 'all'), default='all')
    parser.add_argument('--keep-selection', action='store_true', help='Restart without expanding saved asset selections')
    args = parser.parse_args(argv)
    if not 1 <= args.port <= 65535: parser.error('Port must be between 1 and 65535')
    fetch = partial(request, args.port, args.token)
    try:
        if args.action == 'restart': return restart(args)
        if args.action == 'expand': result = expand(fetch, IDS if args.workspace == 'all' else [args.workspace])
        elif args.action == 'controls':
            state = fetch('/api/engine-control')
            result = {'actions':state.get('actions', []), 'authority':state.get('authority', {})}
        else:
            result = {}
            for key in IDS:
                data = fetch('/api/command-centers/'+key)
                own = data.get('profile', {})
                result[key] = {'assets':own.get('assets'), 'runtime_available':own.get('runtime_available'),
                               'feed':data.get('runtime_feed_mode'), 'paper_pnl':data.get('paper_pnl')}
        print(json.dumps(result, indent=2, allow_nan=False))
        return 0
    except KeyboardInterrupt: return 130
    except (RuntimeError, OSError, ValueError, subprocess.CalledProcessError) as error:
        print('Maintenance incomplete: '+str(error), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
