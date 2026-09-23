# Grok (xAI) — 2026-09-22. Whole file.
from __future__ import annotations
import hashlib, json, os, tempfile
from pathlib import Path
from icarus_engine.ignore_trade import ignored_symbol
from .dataset import attach_labels, load_ohlc, walk_slices
from .families import FAMILIES, family_for
from .logit import KEYS, accuracy, fit
from .catalog import TRADED


def training_signature():
    """CA: invalidate resume caches after feature/trainer or event code changes."""
    root = Path(__file__).parent
    paths = [root / name for name in ('run.py', 'dataset.py', 'logit.py', 'xgb.py', 'families.py')]
    paths.append(root.parent / 'events/calendar.py')
    return hashlib.sha256(''.join(file_hash(p) for p in paths).encode()).hexdigest()

def file_hash(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()

def train_file(path, chart_type: str, schema: str = "ohlc", asset: str = "", *,
               model="baseline", root=None, sensors=None, journal_rows=None,
               provenance=None, options=None):
    if not asset or asset not in TRADED or ignored_symbol(asset):
        return {"status": "ignored", "reason": "only the nine registered execution symbols may be trained",
                "asset": asset, "execution_authorized": False}
    path = Path(path)
    fam_name = family_for(chart_type, schema)
    fam = FAMILIES[fam_name]
    # CA: freeze identity and preserve this family's original order.
    source_sha = file_hash(path)
    bars = load_ohlc(path, strict=True, family=fam_name)
    if len(bars) < fam.min_rows:
        return {"status": "skipped", "reason": f"{len(bars)} rows < min_rows {fam.min_rows}",
                "family": fam_name, "asset": asset, "path": str(path), "execution_authorized": False}
    from icarus_engine.events.calendar import load_events
    events = load_events(root)
    labeled = attach_labels(bars, fam_name, events=events, asset=asset, sensors=sensors)
    if model == "xgb":
        from .xgb import fit_models, chronological_split, validate_artifact
        report = fit_models(labeled, asset=asset, family=fam_name,
                            journal_rows=journal_rows, **(options or {}))
        parts = chronological_split(labeled)
        baseline_rows = [labeled[i] for i in parts['train']]
        baseline = fit(baseline_rows)
        report.update(path=str(path.resolve()), dataset_sha256=source_sha, n_bars=len(bars),
                      n_labeled=len(labeled), chart_type=chart_type, schema=schema,
                      provenance=provenance or {}, author="CA", training_signature=training_signature())
        report['event_sha256'] = hashlib.sha256(json.dumps(events, sort_keys=True).encode()).hexdigest()
        report['feature_policy'] = {'events': 'released_at <= bar.ts; no future surprises',
                                    'sensors': 'explicit available_ts <= bar.ts',
                                    'bars': 'completed family bar; never execution fills'}
        report['baseline'] = {'status': 'fitted', 'kind': 'scaled_l2_logit', 'model': baseline,
                              'features': list(KEYS),
                              'holdout_acc': accuracy(baseline, [labeled[i] for i in parts['holdout']]),
                              'execution_authorized': False}
        if file_hash(path) != source_sha:
            raise ValueError("source CSV changed during fit")
        if not validate_artifact(report, asset=asset, family=fam_name):
            raise ValueError("fitted artifact failed native reload validation")
        return report
    if model != "baseline":
        raise ValueError(f"unknown model {model}")
    try:
        train, valid, hold = walk_slices(len(labeled))
    except ValueError as exc:
        return {"status": "skipped", "reason": str(exc), "family": fam_name, "asset": asset}
    w = fit(labeled[train[0]:train[1]])
    return {
        "status": "fitted", "family": fam_name, "index": fam.index, "label": fam.label,
        "asset": asset, "path": str(path), "dataset_sha256": source_sha,
        "model": w, "author": "CA",
        "n_bars": len(bars), "n_labeled": len(labeled),
        "train_rows": train[1]-train[0], "valid_rows": valid[1]-valid[0], "holdout_rows": hold[1]-hold[0],
        "train_acc": accuracy(w, labeled[train[0]:train[1]]),
        "valid_acc": accuracy(w, labeled[valid[0]:valid[1]]),
        "holdout_acc": accuracy(w, labeled[hold[0]:hold[1]]),
        "execution_authorized": False, "accuracy_guaranteed": False, "notes": fam.notes,
        "limitations": ["Holdout accuracy is descriptive, not a profitability certificate.",
                        "This family must not be concatenated with another family's rows.",
                        "Labels are next-bar on THIS index only."],
    }

def write_report(report, dest: Path):
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    # CA: an interruption must not leave an apparently valid half-written model.
    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=dest.parent,
                                     prefix=dest.name + '.', suffix='.tmp', delete=False) as fh:
        temporary = fh.name
        try:
            json.dump(report, fh, indent=2, allow_nan=False)
            fh.flush()
            os.fsync(fh.fileno())
        except Exception:
            fh.close()
            os.unlink(temporary)
            raise
    os.replace(temporary, dest)
    return dest
