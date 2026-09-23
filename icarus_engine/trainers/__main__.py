# Grok (xAI) — 2026-09-22.
from __future__ import annotations
import argparse, json
from pathlib import Path
from .run import train_file, write_report

def main(argv=None):
    p = argparse.ArgumentParser(description="Fit one Icarus trainer family on one CSV")
    source = p.add_mutually_exclusive_group(required=True)
    source.add_argument("--path")
    source.add_argument("--manifest", help="CA: deterministic catalog manifest, one file per symbol/family")
    p.add_argument("--chart-type")
    p.add_argument("--schema", default="ohlc")
    p.add_argument("--asset", default="")
    p.add_argument("--out", default="")
    p.add_argument("--root", default=".")
    p.add_argument("--model", choices=("baseline", "xgb"), default="baseline")
    p.add_argument("--rounds", type=int, default=160)
    args = p.parse_args(argv)
    if args.manifest:
        return train_manifest(args)
    if not args.chart_type:
        p.error('--chart-type is required with --path')
    report = train_file(args.path, args.chart_type, args.schema, args.asset,
                        model=args.model, root=args.root, options={'num_boost_round': args.rounds})
    if args.out:
        write_report(report, args.out)
    print(json.dumps({k: v for k, v in report.items() if k not in ('primary','agree','regime','failure','model')}, indent=2))
    return 0 if report.get("status") in ("fitted", "skipped") else 1


def train_manifest(args):
    """CA: persist one resumable, validated artifact per selected cell."""
    from .run import file_hash, training_signature
    from .xgb import validate_artifact
    from icarus_engine.events.calendar import load_events
    import hashlib
    event_hash = hashlib.sha256(json.dumps(load_events(args.root), sort_keys=True).encode()).hexdigest()
    manifest = json.loads(Path(args.manifest).read_text(encoding='utf-8'))
    out = Path(args.out or 'run/trainers')
    records = []
    for cell in manifest['selected_cells']:
        asset, family = cell['asset'], cell['family']
        dest = out / f'{asset}_{family}_xgb.json'
        try:
            if file_hash(Path(cell['path'])) != cell['sha256']:
                raise ValueError('source hash differs from catalog')
            report = None
            if dest.is_file():
                cached = json.loads(dest.read_text(encoding='utf-8'))
                if (validate_artifact(cached, asset=asset, family=family)
                        and cached['dataset_sha256'] == cell['sha256']
                        and cached.get('training_signature') == training_signature()
                        and cached.get('event_sha256') == event_hash
                        and cached['options']['num_boost_round'] == args.rounds):
                    report = cached
            if report is None:
                report = train_file(cell['path'], cell['chart_type'], asset=asset,
                                    model='xgb', root=args.root, provenance=cell,
                                    options={'num_boost_round': args.rounds})
                if report['status'] != 'fitted':
                    raise ValueError(report.get('reason', 'not fitted'))
                write_report(report, dest)
            baseline = {**report['baseline'], 'asset': asset, 'family': family,
                        'dataset_sha256': report['dataset_sha256'], 'author': 'CA'}
            write_report(baseline, out / f'{asset}_{family}.json')
            record = {'asset': asset, 'family': family, 'status': 'fitted',
                      'path': str(dest), 'artifact_sha256': file_hash(dest),
                      'holdout_acc': report['holdout_acc'], 'holdout_logloss': report['holdout_logloss'],
                      'auxiliary': {k: report[k]['status'] for k in ('agree','regime','calibration','failure')}}
        except (ValueError, OSError, KeyError) as exc:
            record = {'asset': asset, 'family': family, 'status': 'failed', 'reason': str(exc)}
        records.append(record)
        write_report({'author': 'CA', 'manifest_sha256': file_hash(Path(args.manifest)),
                      'execution_authorized': False, 'cells': records, 'coverage': manifest['coverage']},
                     out / 'training_run.json')
        print(json.dumps(record), flush=True)
    return 1 if any(r['status'] == 'failed' for r in records) else 0

if __name__ == "__main__":
    raise SystemExit(main())
