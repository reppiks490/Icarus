"""CA: replay saved ML evidence against original, unmodified owner CSVs."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

from icarus_engine.events.calendar import load_events

from .dataset import attach_labels, load_ohlc
from .families import family_for
from .run import file_hash, training_signature, write_report
from .xgb import chronological_split, predict_proba, validate_artifact


def verify_cell(cell, model_path, baseline_path, events):
    """Recompute source, chronological split and primary holdout metrics."""
    asset, family = cell["asset"], cell["family"]
    source = Path(cell["path"])
    artifact = json.loads(Path(model_path).read_text(encoding="utf-8"))
    baseline = json.loads(Path(baseline_path).read_text(encoding="utf-8"))
    if not validate_artifact(artifact, asset=asset, family=family):
        raise ValueError("native artifact did not reload")
    source_hash = file_hash(source)
    if (source_hash != cell["sha256"] or artifact.get("dataset_sha256") != source_hash
            or artifact.get("training_signature") != training_signature()
            or artifact.get("event_sha256") != hashlib.sha256(
                json.dumps(events, sort_keys=True).encode()).hexdigest()
            or artifact.get("provenance", {}).get("sha256") != source_hash
            or artifact.get("provenance", {}).get("interval") != cell.get("interval")
            or artifact.get("chart_type") != cell["chart_type"]
            or family_for(cell["chart_type"]) != family):
        raise ValueError("source, code, calendar, or interval provenance differs")
    if (baseline.get("status") != "fitted" or baseline.get("kind") != "scaled_l2_logit"
            or baseline.get("asset") != asset or baseline.get("family") != family
            or baseline.get("dataset_sha256") != source_hash or not baseline.get("model")):
        raise ValueError("separate logit baseline is absent or has wrong identity")
    bars = load_ohlc(source, strict=True, family=family)
    if len(bars) != artifact.get("n_bars"):
        raise ValueError("bar count differs from training")
    if any(k in artifact["features"] for k in ("vix_z", "tnx_z", "dxy_z")):
        raise ValueError("external sensor inputs require their own versioned replay")
    rows = attach_labels(bars, family, events=events, asset=asset)
    if len(rows) != artifact.get("n_labeled"):
        raise ValueError("label count differs from training")
    options = artifact["options"]
    split = chronological_split(
        rows, train_frac=options["train_frac"], valid_frac=options["valid_frac"],
        calibration_frac=options["calibration_frac"], horizon=options["horizon"])
    for name in ("train", "valid", "holdout", "calibration", "evaluation"):
        old, positions = artifact["splits"][name], split[name]
        if (old["rows"] != len(positions)
                or old["first_index"] != rows[positions[0]]["row_index"]
                or old["last_index"] != rows[positions[-1]]["row_index"]
                or old["max_label_index"] != max(rows[i]["label_index"] for i in positions)):
            raise ValueError(f"{name} split differs from training")
    hold = [rows[i] for i in split["holdout"]]
    event_flags = ("fomc", "any_macro", "cpi", "nfp", "earnings")
    positive_events = {name: sum(bool(rows[i]["x"].get(name)) for i in split["train"])
                       for name in event_flags}
    probability = predict_proba(artifact["primary"], hold)
    labels = [row["y"] > 0 for row in hold]
    accuracy = sum((p >= 0.5) == y for p, y in zip(probability, labels)) / len(labels)
    clipped = [max(1e-12, min(1 - 1e-12, p)) for p in probability]
    logloss = -sum(y * math.log(p) + (1 - y) * math.log1p(-p)
                   for y, p in zip(labels, clipped)) / len(labels)
    if (not math.isclose(accuracy, artifact["holdout_acc"], abs_tol=1e-9)
            or not math.isclose(logloss, artifact["holdout_logloss"], abs_tol=1e-7)):
        raise ValueError("holdout metrics differ from native replay")
    return {"asset": asset, "family": family, "status": "verified",
            "source_sha256": source_hash, "artifact_sha256": file_hash(model_path),
            "holdout_rows": len(hold), "holdout_acc": accuracy,
            "holdout_logloss": logloss,
            "train_positive_event_rows": positive_events,
            "unlearned_event_flags": [k for k, count in positive_events.items() if count == 0],
            "execution_authorized": False}


def verify_manifest(manifest_path, out_dir, root):
    manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    selected = manifest["selected_cells"]
    if len({(c["asset"], c["family"]) for c in selected}) != len(selected):
        raise ValueError("duplicate symbol/family in inventory")
    events = load_events(root)
    folder = Path(out_dir)
    records = []
    for cell in selected:
        prefix = f"{cell['asset']}_{cell['family']}"
        try:
            record = verify_cell(cell, folder / f"{prefix}_xgb.json",
                                 folder / f"{prefix}.json", events)
        except (OSError, KeyError, TypeError, ValueError) as exc:
            record = {"asset": cell["asset"], "family": cell["family"],
                      "status": "failed", "reason": str(exc),
                      "execution_authorized": False}
        records.append(record)
    return {"author": "CA", "status": "verified" if all(
                r["status"] == "verified" for r in records) else "failed",
            "cells": records, "execution_authorized": False,
            "manifest_sha256": file_hash(manifest_path)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", default="run/data_inventory.json")
    parser.add_argument("--models", default="run/trainers")
    parser.add_argument("--root", default=".")
    parser.add_argument("--out", default="run/trainers/verification.json")
    args = parser.parse_args(argv)
    report = verify_manifest(args.manifest, args.models, args.root)
    write_report(report, args.out)
    print(json.dumps({"status": report["status"], "cells": len(report["cells"]),
                      "verified": sum(r["status"] == "verified" for r in report["cells"]),
                      "out": args.out}))
    return 0 if report["status"] == "verified" else 1


if __name__ == "__main__":
    raise SystemExit(main())
