# Grok (xAI) — 2026-09-22. Whole file.
from __future__ import annotations
import hashlib, json
from pathlib import Path
from icarus_engine.ignore_trade import ignored_symbol
from icarus_engine.model_log import log_action
from .dataset import attach_labels, walk_slices
from .families import FAMILIES, family_for
from .integrity import inspect_ohlc
from .logit import accuracy, fit
from . import xgb_slot
from icarus_engine.spec import artifact

def file_hash(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()

def _load(path, *, raw_bytes=None, **ids):
    """(bars, manifest, refusal). Claude (Opus 5.5) 2026-09-27: a file the DATA gate blocks, or one that leaves no
    usable row, is reported with its manifest, never trained."""
    def refuse(reason, manifest=None):
        extra = {"dataset_manifest": manifest} if manifest is not None else {}
        return {**ids, "status": "blocked", "reason": reason, "path": str(path), **extra,
                "execution_authorized": False}
    try:
        bars, manifest = inspect_ohlc(path, raw_bytes=raw_bytes)
    except (ValueError, OSError) as exc:
        return None, None, refuse(str(exc))
    if manifest["status"] == "blocked":
        return None, manifest, refuse(manifest["reason"], manifest)
    if not bars:
        return None, manifest, refuse("no usable rows: every timestamp was unparseable or every close missing", manifest)
    return bars, manifest, None

def _preflight(asset, slot):
    if not asset:
        return {"status": "blocked", "reason": f"Slot {slot} needs --asset", "execution_authorized": False}
    if ignored_symbol(asset):
        return {"status": "ignored", "reason": "MBT/SOL/ETHUSD are not traded", "asset": asset,
                "execution_authorized": False}
    return None

def _too_short(bars, fam, fam_name, asset, path, manifest):
    if len(bars) >= fam.min_rows:
        return None
    return {"status": "skipped", "reason": f"{len(bars)} rows < min_rows {fam.min_rows}", "family": fam_name,
            "asset": asset, "path": str(path), "execution_authorized": False, "dataset_manifest": manifest}

def train_file(path, chart_type: str, schema: str = "ohlc", asset: str = "", *, raw_bytes=None):
    if asset and ignored_symbol(asset):
        return {"status": "ignored", "reason": "MBT/SOL/ETHUSD are not traded",
                "asset": asset, "execution_authorized": False}
    path = Path(path)
    fam_name = family_for(chart_type, schema)
    fam = FAMILIES[fam_name]
    bars, manifest, refusal = _load(path, raw_bytes=raw_bytes, family=fam_name, asset=asset, slot="logit")
    if refusal:
        return refusal
    short = _too_short(bars, fam, fam_name, asset, path, manifest)
    if short:
        return short
    labeled = attach_labels(bars, fam_name)
    try:
        train, valid, hold = walk_slices(len(labeled))
    except ValueError as exc:
        return {"status": "skipped", "reason": str(exc), "family": fam_name, "asset": asset,
                "execution_authorized": False, "dataset_manifest": manifest}
    w = fit(labeled[train[0]:train[1]])
    return {
        "status": "fitted", "family": fam_name, "index": fam.index, "label": fam.label,
        "asset": asset, "path": str(path), "dataset_sha256": manifest["raw_sha256"], "dataset_manifest": manifest,
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

def train_xgb_file(path, chart_type: str, schema: str = "ohlc", asset: str = "", out=None, ledger=None, *, raw_bytes=None):
    refusal = _preflight(asset, 1)
    if refusal:
        return refusal
    path = Path(path)
    fam_name = family_for(chart_type, schema)
    fam = FAMILIES[fam_name]
    bars, manifest, refusal = _load(path, raw_bytes=raw_bytes, family=fam_name, asset=asset, slot="xgb")
    if refusal:
        return refusal
    short = _too_short(bars, fam, fam_name, asset, path, manifest)
    if short:
        return short
    return xgb_slot.train(
        attach_labels(bars, fam_name), asset, fam_name,
        out_path=Path(out) if out else Path(artifact(asset, fam_name, "xgb")),
        ledger_path=ledger, dataset_sha256=manifest["raw_sha256"],
        extra={"path": str(path), "index": fam.index, "label": fam.label, "n_bars": len(bars),
               "dataset_manifest": manifest},
    )

def train_rank_file(path, chart_type: str, schema: str = "ohlc", asset: str = "", candidates=None, out=None,
                    ledger=None, root=".", cand_chart=None):
    """cand_chart: the candidates' chart type. Only a clock chart (e.g. 1m, 60m, 1D) gets exact bar timing; any
    other value, or none, treats candidate stamps as minute floors (fail closed)."""
    from icarus_engine.events.calendar import load_events
    from . import rank_slot
    refusal = _preflight(asset, 2)
    if refusal:
        return refusal
    kept = {n: pth for n, pth in (candidates or {}).items() if not ignored_symbol(n)}
    if not kept:
        return {"status": "blocked", "reason": "no candidate series", "asset": asset, "execution_authorized": False}
    path = Path(path)
    fam_name = family_for(chart_type, schema)
    bars, manifest, refusal = _load(path, family=fam_name, asset=asset, slot="rank")
    if refusal:
        return refusal
    series, cand_manifests, refused = {}, {}, {}
    for n, pth in sorted(kept.items()):
        cb, cm, why = _load(pth)
        if why:
            refused[n] = why["reason"]          # a blocked candidate file is left out, and said so
        else:
            series[n], cand_manifests[n] = cb, cm
    if not series:
        return {"status": "blocked", "reason": "every candidate file was refused", "refused_candidates": refused,
                "asset": asset, "execution_authorized": False, "dataset_manifest": manifest}
    exact = bool(cand_chart) and family_for(cand_chart).startswith("clock_")
    rows = rank_slot.rank_rows(bars, series, load_events(root), fam_name, future=asset, floored=not exact)
    return rank_slot.train(
        rows, asset, fam_name,
        out_path=Path(out) if out else Path(artifact(asset, fam_name, "rank")),
        ledger_path=ledger,
        extra={"path": str(path), "dataset_sha256": manifest["raw_sha256"], "dataset_manifest": manifest,
               "candidate_sha256": {n: cand_manifests[n]["raw_sha256"] for n in series},
               "candidate_manifests": cand_manifests, "refused_candidates": refused,
               "candidate_timing": "exact clock stamps" if exact else "minute-floored stamps"},
    )

def write_report(report, dest: Path):
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(report, indent=2, allow_nan=False))
    log_action("trainer", f"wrote {dest}", json.dumps({k: report.get(k) for k in
                ("status", "asset", "family", "holdout_acc", "slot")}, default=str))
    return dest
