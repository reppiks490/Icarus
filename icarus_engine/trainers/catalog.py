"""CA: owner archive provenance and deterministic, per-file training selection."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import subprocess
import zipfile
from collections import Counter
from pathlib import Path, PurePosixPath

from icarus_engine.unzip_batches import BATCHES, _classify
from .dataset import load_ohlc
from .families import FAMILIES

TRADED = ('NQ', 'ES', 'YM', 'GC', 'SI', 'PL', 'PA', 'BTCF', 'BTC')
OLDER = ('Full csv candles only.zip', 'Csv files for different chart types.zip',
         'More csv by ticks with chart candle and volume profiles technicals built in.zip')


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def identify(name, archive):
    """Explicit exchange and interval tokens only; numeric chart exports can be ambiguous."""
    m = re.fullmatch(r'(.+),\s*([^ ]+)(?: \d+)?\.csv', name, flags=re.I)
    if not m:
        return {'status': 'unidentified', 'reason': 'unknown filename schema'}
    instrument, interval = m.groups()
    futures = re.fullmatch(r'(CME_MINI|CME|CBOT_MINI|COMEX|NYMEX)(?:_DL)?_(NQ|ES|YM|GC|SI|PL|PA|BTC)1!', instrument, re.I)
    spot = re.fullmatch(r'(COINBASE|BITSTAMP)_BTCUSD', instrument, re.I)
    if futures:
        venue, root = (v.upper() for v in futures.groups())
        expected = {'NQ': 'CME_MINI', 'ES': 'CME_MINI', 'YM': 'CBOT_MINI',
                    'GC': 'COMEX', 'SI': 'COMEX', 'PL': 'NYMEX', 'PA': 'NYMEX', 'BTC': 'CME'}
        if venue != expected[root]:
            return {'status': 'unidentified', 'reason': 'exchange/symbol mismatch'}
        asset = 'BTCF' if root == 'BTC' else root
    elif spot:
        asset, venue = 'BTC', spot.group(1).upper()
    else:
        return {'status': 'not_execution', 'instrument': instrument, 'interval': interval}
    result = {'asset': asset, 'venue': venue, 'instrument': instrument, 'interval': interval}
    token = interval.upper()
    if token.endswith('T') and token[:-1].isdigit():
        chart = 'tick'
    elif token.endswith('R') and token[:-1].isdigit():
        chart = 'range'
    elif archive != 'Full csv candles only.zip':
        return {**result, 'status': 'ambiguous', 'reason': 'chart family not encoded in filename; owner mapping required'}
    elif token.endswith('S') and token[:-1].isdigit():
        chart = 'seconds'
    elif token in ('D', '1D'):
        chart = 'daily'
    elif token in ('W', '1W'):
        chart = 'weekly'
    elif token.endswith('M'):
        return {**result, 'status': 'unsupported', 'reason': 'monthly, not minute bars'}
    elif token.isdigit() and int(token) > 0:
        chart = 'hours' if int(token) >= 60 else 'minutes'
    else:
        return {**result, 'status': 'unsupported', 'reason': 'unrecognized explicit interval'}
    family = {'minutes': 'clock_minutes', 'hours': 'clock_hours', 'seconds': 'clock_seconds',
              'daily': 'clock_daily', 'weekly': 'clock_weekly'}.get(chart, chart)
    return {**result, 'status': 'identified', 'chart_type': chart, 'family': family,
            'chart_evidence': 'explicit T/R suffix' if chart in ('tick', 'range') else 'owner archive explicitly named candles only'}


def extract_archive(path, target):
    """Extract only regular CSV entries without rewriting existing differing files."""
    records = []
    with zipfile.ZipFile(path) as archive:
        for entry in archive.infolist():
            member = PurePosixPath(entry.filename.replace('\\', '/'))
            if entry.is_dir() or member.suffix.lower() != '.csv' or any(p.startswith(('.', '__MACOSX')) for p in member.parts):
                continue
            if member.is_absolute() or '..' in member.parts or any(':' in p for p in member.parts):
                raise ValueError(f'unsafe archive member: {entry.filename}')
            if entry.file_size > 100 << 20 or (entry.external_attr >> 16) & 0o170000 == 0o120000:
                raise ValueError(f'unsupported archive member: {entry.filename}')
            data = archive.read(entry)
            sha = hashlib.sha256(data).hexdigest()
            dest = Path(target).joinpath(*member.parts)
            if dest.exists() and digest(dest) != sha:
                raise ValueError(f'existing differing export: {dest}')
            dest.parent.mkdir(parents=True, exist_ok=True)
            if not dest.exists():
                dest.write_bytes(data)
            records.append({'archive': Path(path).name, 'member': entry.filename,
                            'path': str(dest.resolve()), 'sha256': sha, 'bytes': len(data)})
    return records


def inventory(src, plant):
    src, plant = Path(src).resolve(), Path(plant).resolve()
    six = []
    for name in BATCHES:
        path = src / name
        verified = 0
        with zipfile.ZipFile(path) as archive:
            for entry in archive.infolist():
                base = PurePosixPath(entry.filename).name
                if entry.is_dir() or not base.lower().endswith('.csv') or base.startswith('.'):
                    continue
                dest = plant / 'history/unzipped' / _classify(base) / base
                sha = hashlib.sha256(archive.read(entry)).hexdigest()
                if not dest.is_file() or digest(dest) != sha:
                    raise ValueError(f'six-batch verification failed: {name}/{base}')
                verified += 1
        six.append({'archive': name, 'sha256': digest(path), 'verified_csvs': verified})
    rows = []
    for name in OLDER:
        path = src / name
        if not path.is_file():
            continue
        extracted = extract_archive(path, plant / 'history/unzipped/training_sources' / path.stem)
        for rec in extracted:
            info = identify(Path(rec['path']).name, name)
            row = {**rec, **info, 'archive_sha256': digest(path)}
            if info['status'] == 'identified':
                try:
                    bars = load_ohlc(Path(rec['path']), strict=True, family=info['family'])
                    with Path(rec['path']).open(encoding='utf-8-sig', newline='') as fh:
                        row['columns'] = next(csv.reader(fh))
                    row.update(rows=len(bars), first_ts=bars[0]['ts'], last_ts=bars[-1]['ts'])
                    row['status'] = 'eligible_data' if len(bars) >= FAMILIES[info['family']].min_rows else 'insufficient_rows'
                except ValueError as exc:
                    row.update(status='invalid_data', reason=str(exc))
            rows.append(row)
    selected, coverage = [], []
    for asset in TRADED:
        for family in FAMILIES:
            eligible = [r for r in rows if r.get('asset') == asset and r.get('family') == family and r['status'] == 'eligible_data']
            eligible.sort(key=lambda r: (-r['rows'], -(r['last_ts'] - r['first_ts']), r['path']))
            if eligible:
                selected.append(eligible[0])
                coverage.append({'asset': asset, 'family': family, 'status': 'selected', 'sha256': eligible[0]['sha256'], 'alternatives': len(eligible)-1})
            else:
                coverage.append({'asset': asset, 'family': family, 'status': 'no_valid_identified_csv',
                                 'ambiguous_exports': sum(r.get('asset') == asset and r['status'] == 'ambiguous' for r in rows)})
    rev = subprocess.run(['git', '-C', str(src), 'rev-parse', 'HEAD'], capture_output=True, text=True, check=True).stdout.strip()
    return {'author': 'CA', 'source_commit': rev, 'six_batches': six, 'files': rows,
            'selected_cells': selected, 'coverage': coverage,
            'selection_rule': 'most valid rows, then longest time coverage, then stable path; no outcome selection',
            'execution_authorized': False, 'ingested_to_historyhub': False,
            'status_counts': dict(Counter(r['status'] for r in rows))}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--src', default='history/unzipped/_repo')
    parser.add_argument('--plant', default='.')
    parser.add_argument('--out', default='run/data_inventory.json')
    args = parser.parse_args(argv)
    report = inventory(args.src, args.plant)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, allow_nan=False), encoding='utf-8')
    print(json.dumps({'selected_cells': len(report['selected_cells']), 'status_counts': report['status_counts'], 'out': str(out)}, indent=2))


if __name__ == '__main__':
    main()
