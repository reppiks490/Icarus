# Grok (xAI) — 2026-09-22. Whole file.
from __future__ import annotations
import hashlib, json
from pathlib import Path
from icarus_engine.ignore_trade import ignored_symbol
from .dataset import attach_labels, load_ohlc, walk_slices
from .families import FAMILIES, family_for
from .logit import accuracy, fit

def file_hash(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()

def train_file(path, chart_type: str, schema: str = "ohlc", asset: str = ""):
    if asset and ignored_symbol(asset):
        return {"status": "ignored", "reason": "MBT/SOL/ETHUSD are not traded",
                "asset": asset, "execution_authorized": False}
    path = Path(path)
    fam_name = family_for(chart_type, schema)
    fam = FAMILIES[fam_name]
    bars = load_ohlc(path)
    if len(bars) < fam.min_rows:
        return {"status": "skipped", "reason": f"{len(bars)} rows < min_rows {fam.min_rows}",
                "family": fam_name, "asset": asset, "path": str(path)}
    labeled = attach_labels(bars, fam_name)
    try:
        train, valid, hold = walk_slices(len(labeled))
    except ValueError as exc:
        return {"status": "skipped", "reason": str(exc), "family": fam_name, "asset": asset}
    w = fit(labeled[train[0]:train[1]])
    return {
        "status": "fitted", "family": fam_name, "index": fam.index, "label": fam.label,
        "asset": asset, "path": str(path), "dataset_sha256": file_hash(path),
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
    dest.write_text(json.dumps(report, indent=2, allow_nan=False))
    return dest
