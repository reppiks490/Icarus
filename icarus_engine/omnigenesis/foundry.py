"""Bounded, deterministic hypothesis foundry for one-feature event research.

Real chronological splits, label-maturity purges and a frozen final holdout.
Statistical success never grants execution, auto-promotion, or causal proof.
No arbitrary Python expressions or model-provided source code are evaluated.
"""
from __future__ import annotations

from .contracts import identity, normalize_dataset


def _probability(rows: list[dict]) -> float:
    return (1 + sum(int(row["outcome"]) for row in rows)) / (len(rows) + 2)


def _brier(probabilities: list[float], rows: list[dict]) -> float:
    if not rows or len(probabilities) != len(rows):
        raise ValueError("invalid scoring inputs")
    return sum((p - int(row["outcome"])) ** 2
               for p, row in zip(probabilities, rows)) / len(rows)


def _transform(value: float, operation: str) -> float:
    if operation == "raw":
        return value
    if operation == "absolute":
        return abs(value)
    raise ValueError("unsupported transform")


def _train_candidate(rows: list[dict], operation: str, threshold: float):
    positive = [row for row in rows
                if _transform(row["feature"], operation) >= threshold]
    negative = [row for row in rows
                if _transform(row["feature"], operation) < threshold]
    if min(len(positive), len(negative)) < 4:
        return None
    return {
        "operation": operation, "threshold": threshold,
        "p_ge": _probability(positive), "p_lt": _probability(negative),
        "train_ge": len(positive), "train_lt": len(negative),
    }


def _predict(candidate: dict, rows: list[dict]) -> list[float]:
    return [candidate["p_ge"] if _transform(row["feature"],
            candidate["operation"]) >= candidate["threshold"]
            else candidate["p_lt"] for row in rows]


def _quantiles(rows: list[dict], op: str) -> list[float]:
    values = sorted(_transform(row["feature"], op) for row in rows)
    return sorted({values[int((len(values) - 1) * q / 10)]
                   for q in range(1, 10)})


def evaluate_dataset(dataset: dict) -> dict:
    """Propose one screened hypothesis; never claim proven market edge.

    Caller supplies historical as-of features and subsequently resolved event
    labels. The system only uses train features to generate candidates, train
    labels to fit probabilities, and validation labels to select a single
    candidate before examining the protected holdout.
    """
    ds = normalize_dataset(dataset)
    rows = ds["records"]
    n = len(rows)
    first_val, first_hold = int(0.6 * n), int(0.8 * n)
    val_start = rows[first_val]["decision_at"]
    hold_start = rows[first_hold]["decision_at"]
    # Purge any outcome unavailable before the next split. Strict comparison
    # is conservative at the exact boundary and avoids same-timestamp ambiguity.
    train = [r for r in rows[:first_val] if r["label_resolved_at"] < val_start]
    validation = [r for r in rows[first_val:first_hold]
                  if r["label_resolved_at"] < hold_start]
    holdout = rows[first_hold:]
    if min(len(train), len(validation), len(holdout)) < 8:
        raise ValueError("insufficient mature data after chronological purge")

    base_p = _probability(train)
    baseline_validation = _brier([base_p] * len(validation), validation)
    baseline_holdout = _brier([base_p] * len(holdout), holdout)
    candidates = []
    seen = set()
    for operation in ("raw", "absolute"):
        for threshold in _quantiles(train, operation):
            cand = _train_candidate(train, operation, threshold)
            if cand is None:
                continue
            key = (operation, threshold)
            if key in seen:
                continue
            seen.add(key)
            cand["validation_brier"] = _brier(_predict(cand, validation),
                                              validation)
            candidates.append(cand)
    if not candidates:
        raise ValueError("no admissible candidate, insufficient feature diversity")
    # Score every candidate on validation only; frozen holdout is never used
    # for ranking. Tie-breaks are deterministic.
    candidates.sort(key=lambda c: (c["validation_brier"],
                    c["operation"], c["threshold"]))
    winner = candidates[0]
    holdout_brier = _brier(_predict(winner, holdout), holdout)
    improvement = baseline_holdout - holdout_brier
    status = ("EXPLORATORY" if improvement > 0 else "REJECTED")
    dataset_sha = identity(ds)
    report = {
        "schema_version": "icarus-omnigenesis-study-v1",
        "dataset_id": ds["dataset_id"],
        "source_commit": ds["source_commit"],
        "dataset_sha256": dataset_sha,
        "asset": rows[0]["asset"],
        "kind": "one_feature_event_probability",
        "status": status,
        "authority": {"research_only": True,
                      "execution_authorized": False,
                      "production_decision_authorized": False,
                      "auto_promote": False},
        "scientific_limits": [
            "observational association, not causal identification",
            "single held-out segment, not independent replication",
            "no multiple-market or multi-family qualification",
            "no execution cost, spread, slippage, or latency proof",
            "never a live trading signal",
        ],
        "data_counts": {
            "total": n, "train_mature": len(train),
            "validation_mature": len(validation), "holdout": len(holdout),
            "train_purged": first_val - len(train),
            "validation_purged": first_hold - first_val - len(validation),
        },
        "split_boundaries": {"validation_start": val_start,
                             "holdout_start": hold_start},
        "search": {"candidate_count": len(candidates),
                   "search_budget": 18,
                   "selection": "minimum validation Brier (holdout unseen)"},
        "baseline": {"train_probability": base_p,
                     "validation_brier": baseline_validation,
                     "holdout_brier": baseline_holdout},
        "hypothesis": {
            "operation": winner["operation"], "threshold": winner["threshold"],
            "p_ge": winner["p_ge"], "p_lt": winner["p_lt"],
            "train_ge": winner["train_ge"], "train_lt": winner["train_lt"],
            "validation_brier": winner["validation_brier"],
            "holdout_brier": holdout_brier,
            "holdout_brier_improvement": improvement,
        },
        "validation_required": [
            "independent forward data", "sequential inference or multiplicity gate",
            "cost-sensitive trade evaluation", "cross-regime stability",
            "independent scientific review",
        ],
    }
    report["study_id"] = identity(report)
    return report
