"""A strict observational *adapter* for synthetic UMBRA paired-world outputs.

The adapter checks UMBRA v5 pairedExperiment aggregate arithmetic, seed
derivation, field contracts and within-file content integrity. It cannot
recompute the UMBRA civilization engine, establish creator authenticity,
empirically calibrate economics or authorize a trade. No runtime imports from
UMBRA or execution modules are made; the original UMBRA repo stays distinct.
"""
from __future__ import annotations

import hashlib
import math
from typing import Any, Mapping

from .contracts import identity

_AUTHORITY = {"research_only": True, "execution_authorized": False,
              "production_decision_authorized": False, "auto_promote": False}
_POLICIES = {"trade", "climate", "medicine", "innovation", "migration",
             "conservation", "conflict"}
_REPORT_FIELDS = {"version", "seed", "trials", "steps", "baseline", "treatment",
                  "mean", "median", "p05", "p95", "sd", "positive", "paths"}
_PATH_FIELDS = {"seed", "baseline", "treatment", "diff",
                "foodDiff", "emissionsDiff"}


def _number(value: Any) -> float:
    if type(value) not in (int, float):
        raise ValueError("numeric field must not be a boolean or text")
    try:
        number = float(value)
    except (OverflowError, ValueError) as exc:
        raise ValueError("invalid numeric field") from exc
    if not math.isfinite(number):
        raise ValueError("nonfinite worldline measure")
    return number


def _hash32(n: int) -> int:
    n &= 0xffffffff
    n = ((n ^ (n >> 16)) * 0x7feb352d) & 0xffffffff
    n = ((n ^ (n >> 15)) * 0x846ca68b) & 0xffffffff
    return (n ^ (n >> 16)) & 0xffffffff


def _quantile(values: list[float], q: float) -> float:
    order = sorted(values)
    k = q * (len(order) - 1)
    floor = math.floor(k)
    return order[floor] + (order[math.ceil(k)] - order[floor]) * (k - floor)


def _round_js(v: float, ndigits: int = 2) -> float:
    # pairedExperiment uses +Number.toFixed(2); tolerance accounts for
    # tiny cross-language float differences only, never large discrepancies.
    return round(v, ndigits)


def audit_umbra_worldlines(report: Mapping[str, Any], *,
                          claimed_source_commit: str) -> dict:
    """Verify internal paired-run arithmetic and isolate its synthetic nature.

    A source commit is a caller-supplied identifier, NOT a verified checkout or
    a vendor receipt. The report may be arbitrarily forged while retaining
    internal arithmetic, so all empirical and source-validation gates stay OFF.
    """
    if not isinstance(report, Mapping) or set(report) != _REPORT_FIELDS:
        raise ValueError("unexpected UMBRA report schema")
    if report["version"] != "5.0.0":
        raise ValueError("unsupported UMBRA engine version")
    if (not isinstance(claimed_source_commit, str)
            or len(claimed_source_commit) != 40
            or any(c not in "0123456789abcdef" for c in claimed_source_commit)):
        raise ValueError("claimed source commit must be 40 lowercase hex")
    seed, trials, steps = report["seed"], report["trials"], report["steps"]
    if type(seed) is not int or not 0 <= seed <= 0xffffffff:
        raise ValueError("invalid UMBRA seed")
    if type(trials) is not int or not 2 <= trials <= 64:
        raise ValueError("invalid UMBRA trials")
    if type(steps) is not int or not 1 <= steps <= 2000:
        raise ValueError("invalid UMBRA horizon")
    for name in ("baseline", "treatment"):
        p = report[name]
        if not isinstance(p, Mapping) or set(p) != _POLICIES:
            raise ValueError("unrecognized UMBRA policy")
        if any(not 0 <= _number(value) <= 1 for value in p.values()):
            raise ValueError("policy value outside zero-one interval")
    paths = report["paths"]
    if not isinstance(paths, list) or len(paths) != trials:
        raise ValueError("UMBRA replicate count mismatch")
    diffs = []
    found_seeds = set()
    for idx, row in enumerate(paths):
        if not isinstance(row, Mapping) or set(row) != _PATH_FIELDS:
            raise ValueError("invalid UMBRA replicate schema")
        expected_seed = _hash32(seed + ((idx + 1) * 0x9e3779b1))
        if type(row["seed"]) is not int or row["seed"] != expected_seed or row["seed"] in found_seeds:
            raise ValueError("UMBRA replicate seed divergence")
        found_seeds.add(row["seed"])
        base = _number(row["baseline"])
        treatment = _number(row["treatment"])
        diff = _number(row["diff"])
        food = _number(row["foodDiff"])
        carbon = _number(row["emissionsDiff"])
        if min(base, treatment) < 0 or min(food, carbon) < -1_000_000_000:
            raise ValueError("invalid synthetic measure")
        if not math.isclose(diff, base - treatment, rel_tol=1e-12, abs_tol=1e-7):
            raise ValueError("inconsistent UMBRA paired effect")
        diffs.append(diff)
    def near(a: Any, b: float, name: str) -> None:
        if not math.isclose(_number(a), b, rel_tol=0, abs_tol=0.011):
            raise ValueError("inconsistent UMBRA aggregate " + name)
    mean = sum(diffs) / trials
    near(report["mean"], _round_js(mean), "mean")
    near(report["median"], _round_js(_quantile(diffs, .5)), "median")
    near(report["p05"], _round_js(_quantile(diffs, .05)), "p05")
    near(report["p95"], _round_js(_quantile(diffs, .95)), "p95")
    sd = math.sqrt(sum((d - mean) ** 2 for d in diffs) / (trials - 1))
    near(report["sd"], _round_js(sd), "sd")
    if type(report["positive"]) is not int or report["positive"] != sum(x > 0 for x in diffs):
        raise ValueError("inconsistent UMBRA positive count")
    normalized = {key: report[key] for key in sorted(_REPORT_FIELDS)}
    receipt = {
        "schema_version": "icarus-omnigenesis-umbra-adapter-v1",
        "source_system": "UMBRA_SOVEREIGN_WORLDS_V5",
        "evidence_kind": "SYNTHETIC_MODEL_INTERNAL",
        "authority": dict(_AUTHORITY),
        "claimed_source_commit": claimed_source_commit,
        "source_commit_verified": False,
        "engine_replay_verified": False,
        "model_empirically_calibrated": False,
        "real_market_fidelity_verified": False,
        "report_sha256": identity(normalized),
        "seed": seed,
        "trials": trials,
        "steps": steps,
        "mean_internal_effect": _number(report["mean"]),
        "positive_replicates": report["positive"],
        "all_seed_and_aggregate_checks_passed": True,
        "production_qualified": False,
    }
    receipt["receipt_id"] = identity(receipt)
    return receipt
