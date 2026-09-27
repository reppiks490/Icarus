# Grok (xAI) — 2026-09-22. Whole file.
from __future__ import annotations
import hashlib, json
from pathlib import Path
from icarus_engine.ignore_trade import ignored_symbol
from icarus_engine.model_log import log_action
from .dataset import attach_labels, load_ohlc, walk_slices
from .families import FAMILIES, family_for
from .logit import accuracy, fit
from . import ledger as holdout_ledger, xgb_slot
from icarus_engine.spec import artifact

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
                "family": fam_name, "asset": asset, "path": str(path), "execution_authorized": False}
    labeled = attach_labels(bars, fam_name)
    try:
        train, valid, hold = walk_slices(len(labeled))
    except ValueError as exc:
        return {"status": "skipped", "reason": str(exc), "family": fam_name, "asset": asset,
                "execution_authorized": False}
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
        "slot": "logit",
        "limitations": ["Holdout accuracy is descriptive, not a profitability certificate.",
                        "This family must not be concatenated with another family's rows.",
                        "Labels are next-bar on THIS index only."],
    }

def train_xgb_file(path, chart_type: str, schema: str = "ohlc", asset: str = "", out=None, ledger=None):
    if not asset:
        return {"status": "blocked", "reason": "Slot 1 needs --asset", "execution_authorized": False}
    if ignored_symbol(asset):
        return {"status": "ignored", "reason": "MBT/SOL/ETHUSD are not traded",
                "asset": asset, "execution_authorized": False}
    path = Path(path)
    fam_name = family_for(chart_type, schema)
    fam = FAMILIES[fam_name]
    bars = load_ohlc(path)
    if len(bars) < fam.min_rows:
        return {"status": "skipped", "reason": f"{len(bars)} rows < min_rows {fam.min_rows}",
                "family": fam_name, "asset": asset, "path": str(path), "execution_authorized": False}
    return xgb_slot.train(
        attach_labels(bars, fam_name), asset, fam_name,
        out_path=Path(out) if out else Path(artifact(asset, fam_name, "xgb")),
        ledger_path=Path(ledger) if ledger else Path(holdout_ledger.LEDGER),
        dataset_sha256=file_hash(path),
        extra={"path": str(path), "index": fam.index, "label": fam.label, "n_bars": len(bars)},
    )

def train_rank_file(path, chart_type: str, schema: str = "ohlc", asset: str = "", candidates=None, out=None,
                    ledger=None, root="."):
    from icarus_engine.events.calendar import load_events
    from . import rank_slot
    if not asset:
        return {"status": "blocked", "reason": "Slot 2 needs --asset", "execution_authorized": False}
    if ignored_symbol(asset):
        return {"status": "ignored", "reason": "MBT/SOL/ETHUSD are not traded",
                "asset": asset, "execution_authorized": False}
    kept = {n: pth for n, pth in (candidates or {}).items() if not ignored_symbol(n)}
    if not kept:
        return {"status": "skipped", "reason": "no candidate series", "asset": asset, "execution_authorized": False}
    path = Path(path)
    fam_name = family_for(chart_type, schema)
    rows = rank_slot.rank_rows(load_ohlc(path), {n: load_ohlc(pth) for n, pth in kept.items()},
                               load_events(root), fam_name, future=asset)
    return rank_slot.train(
        rows, asset, fam_name,
        out_path=Path(out) if out else Path(artifact(asset, fam_name, "rank")),
        ledger_path=Path(ledger) if ledger else Path(holdout_ledger.LEDGER),
        extra={"path": str(path), "dataset_sha256": file_hash(path),
               "candidate_sha256": {n: file_hash(pth) for n, pth in sorted(kept.items())}},
    )

def write_report(report, dest: Path):
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(report, indent=2, allow_nan=False))
    log_action("trainer", f"wrote {dest}", json.dumps({k: report.get(k) for k in
                ("status", "asset", "family", "holdout_acc", "slot")}, default=str))
    return dest
