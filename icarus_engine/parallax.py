"""PARALLAX counterfactual twin engine.

Research/shadow-only decision replay ledger. It records the decision that ICARUS
actually made plus explicitly observed alternate outcomes. It never fabricates
counterfactual returns, mutates strategy inputs, places orders, or grants
production authority.

V2 adds an explicit comparison contract, exact-code/context evidence isolation,
evidence-complete paired screening, approximate one-sided significance screening
with Benjamini-Hochberg FDR control, context-strata diagnostics, and richer
counterfactual branch families. These are hypothesis screens, not causal proof.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

SCHEMA_VERSION = "icarus-parallax-v2"
DECISION_SCHEMA = "icarus-parallax-decision-v1"
OUTCOME_SCHEMA = "icarus-parallax-outcome-v1"
_ALLOWED_ACTIONS = {"long", "short", "flat", "abstain"}
_DERIVED_STRATA_KEYS = (
    "session",
    "daypart",
    "volatility_regime",
    "liquidity_regime",
    "macro_regime",
    "trend_regime",
)
_LOCK = threading.RLock()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _finite(value: Any, field: str) -> float:
    if type(value) not in (int, float):
        raise ValueError(f"{field} must be numeric")
    value = float(value)
    if not math.isfinite(value):
        raise ValueError(f"{field} must be finite")
    return value


def _text(value: Any, field: str, limit: int, required: bool = True) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be a string")
    value = value.strip()
    if required and not value:
        raise ValueError(f"{field} is required")
    if len(value) > limit:
        raise ValueError(f"{field} exceeds {limit} characters")
    return value


def _optional_text(value: Any, field: str, limit: int) -> str:
    if value is None:
        return ""
    return _text(value, field, limit, required=False)


def _json(value: Any, field: str, max_bytes: int = 131072) -> str:
    try:
        raw = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError) as ex:
        raise ValueError(f"{field} must be finite JSON") from ex
    if len(raw.encode("utf-8")) > max_bytes:
        raise ValueError(f"{field} exceeds {max_bytes} bytes")
    return raw


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _exact_git_sha(value: Any) -> str:
    value = _text(value, "source_commit", 40).lower()
    if len(value) != 40 or any(c not in "0123456789abcdef" for c in value):
        raise ValueError("source_commit must be an exact 40-character Git SHA")
    return value


def _normalize_contract(raw: Any) -> dict[str, Any]:
    if raw is None:
        raw = {}
    if not isinstance(raw, Mapping):
        raise ValueError("comparison_contract must be an object")
    allowed = {
        "utility_metric",
        "evaluation_horizon_bars",
        "dataset_id",
        "cost_model_id",
        "clock_id",
        "normalization",
    }
    unknown = set(raw) - allowed
    if unknown:
        raise ValueError("unsupported comparison_contract fields: " + ", ".join(sorted(str(x) for x in unknown)))
    horizon = raw.get("evaluation_horizon_bars")
    if horizon is not None:
        if type(horizon) is not int or not 1 <= horizon <= 1_000_000:
            raise ValueError("comparison_contract.evaluation_horizon_bars must be an integer from 1 to 1000000")
    return {
        "utility_metric": _optional_text(raw.get("utility_metric"), "comparison_contract.utility_metric", 80) or "unspecified",
        "evaluation_horizon_bars": horizon,
        "dataset_id": _optional_text(raw.get("dataset_id"), "comparison_contract.dataset_id", 180),
        "cost_model_id": _optional_text(raw.get("cost_model_id"), "comparison_contract.cost_model_id", 180),
        "clock_id": _optional_text(raw.get("clock_id"), "comparison_contract.clock_id", 180),
        "normalization": _optional_text(raw.get("normalization"), "comparison_contract.normalization", 80) or "unspecified",
    }


def _contract_complete(contract: Mapping[str, Any]) -> bool:
    return (
        bool(str(contract.get("utility_metric") or "").strip())
        and contract.get("utility_metric") != "unspecified"
        and type(contract.get("evaluation_horizon_bars")) is int
        and int(contract["evaluation_horizon_bars"]) > 0
        and bool(str(contract.get("dataset_id") or "").strip())
        and bool(str(contract.get("cost_model_id") or "").strip())
        and bool(str(contract.get("clock_id") or "").strip())
    )


def _normalize_strata(raw: Any, context: Mapping[str, Any]) -> dict[str, str]:
    if raw is None:
        raw = {key: context[key] for key in _DERIVED_STRATA_KEYS if key in context}
    if not isinstance(raw, Mapping):
        raise ValueError("strata must be an object")
    if len(raw) > 8:
        raise ValueError("strata may contain at most 8 dimensions")
    out: dict[str, str] = {}
    for key, value in raw.items():
        key_text = _text(str(key), "strata key", 48).lower()
        if isinstance(value, bool):
            value_text = "true" if value else "false"
        elif isinstance(value, str):
            value_text = _text(value, f"strata.{key_text}", 96)
        elif type(value) in (int, float):
            if type(value) is float and not math.isfinite(value):
                raise ValueError(f"strata.{key_text} must be finite")
            value_text = str(value)
        else:
            raise ValueError(f"strata.{key_text} must be a string, number, or boolean")
        out[key_text] = value_text
    return dict(sorted(out.items()))


def _evidence_list(raw: Any) -> list[str]:
    if raw is None:
        return []
    if not isinstance(raw, list):
        return []
    return [str(x) for x in raw if isinstance(x, str) and x.strip()]


class ParallaxStore:
    """Durable paired counterfactual ledger with fail-closed authority."""

    def __init__(self, base_dir: str | os.PathLike[str]):
        self.base_dir = Path(base_dir)
        self.path = self.base_dir / "research" / "parallax.sqlite3"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init()

    def _connect(self) -> sqlite3.Connection:
        con = sqlite3.connect(str(self.path), timeout=15)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA journal_mode=WAL")
        con.execute("PRAGMA foreign_keys=ON")
        return con

    def _init(self) -> None:
        with _LOCK, self._connect() as con:
            con.executescript(
                """
                CREATE TABLE IF NOT EXISTS decisions (
                    decision_id TEXT PRIMARY KEY,
                    observed_at TEXT NOT NULL,
                    asset TEXT NOT NULL,
                    action TEXT NOT NULL,
                    regime TEXT NOT NULL,
                    source_commit TEXT NOT NULL,
                    context_hash TEXT NOT NULL,
                    context_json TEXT NOT NULL,
                    votes_json TEXT NOT NULL,
                    contract_json TEXT NOT NULL DEFAULT '{}',
                    strata_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS branches (
                    branch_id TEXT PRIMARY KEY,
                    decision_id TEXT NOT NULL REFERENCES decisions(decision_id) ON DELETE CASCADE,
                    kind TEXT NOT NULL,
                    label TEXT NOT NULL,
                    params_json TEXT NOT NULL,
                    utility REAL,
                    metrics_json TEXT,
                    evidence_json TEXT,
                    observed_at TEXT,
                    status TEXT NOT NULL DEFAULT 'pending'
                );
                CREATE INDEX IF NOT EXISTS idx_parallax_decisions_asset ON decisions(asset, observed_at);
                CREATE INDEX IF NOT EXISTS idx_parallax_branches_decision ON branches(decision_id, kind);
                """
            )
            columns = {row["name"] for row in con.execute("PRAGMA table_info(decisions)").fetchall()}
            if "contract_json" not in columns:
                con.execute("ALTER TABLE decisions ADD COLUMN contract_json TEXT NOT NULL DEFAULT '{}'")
            if "strata_json" not in columns:
                con.execute("ALTER TABLE decisions ADD COLUMN strata_json TEXT NOT NULL DEFAULT '{}'")

    @staticmethod
    def _default_branches(action: str, votes: Mapping[str, Any]) -> list[dict[str, Any]]:
        branches: list[dict[str, Any]] = [
            {"kind": "actual", "label": "actual", "params": {"action": action}},
        ]
        if action not in {"long", "short"}:
            return branches

        branches.extend(
            [
                {"kind": "skip", "label": "skip", "params": {"action": "abstain"}},
                {"kind": "opposite", "label": "opposite", "params": {"action": "short" if action == "long" else "long"}},
            ]
        )
        for bars in (1, 2, 3, 5):
            branches.append({"kind": "delay", "label": f"delay_{bars}", "params": {"delay_bars": bars}})
        for mult in (0.75, 1.25, 1.50):
            branches.append({"kind": "stop", "label": f"stop_{mult:.2f}", "params": {"stop_multiplier": mult}})
        for mult in (0.50, 1.50):
            branches.append({"kind": "size", "label": f"size_{mult:.2f}", "params": {"size_multiplier": mult}})
        for mult in (0.75, 1.25, 1.50):
            branches.append({"kind": "target", "label": f"target_{mult:.2f}", "params": {"target_multiplier": mult}})

        compounds = (
            ("delay1_stop1.25", {"delay_bars": 1, "stop_multiplier": 1.25}),
            ("delay2_stop1.25", {"delay_bars": 2, "stop_multiplier": 1.25}),
            ("delay1_target1.25", {"delay_bars": 1, "target_multiplier": 1.25}),
            ("stop1.25_target1.25", {"stop_multiplier": 1.25, "target_multiplier": 1.25}),
            ("delay1_stop1.25_target1.25", {"delay_bars": 1, "stop_multiplier": 1.25, "target_multiplier": 1.25}),
        )
        for label, params in compounds:
            branches.append({"kind": "compound", "label": label, "params": params})

        for name in sorted(str(k).strip().lower() for k in votes if str(k).strip())[:24]:
            branches.append({"kind": "ablation", "label": f"without_{name}", "params": {"remove_subsystem": name}})
        return branches

    def record_decision(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        if not isinstance(payload, Mapping):
            raise ValueError("decision must be an object")
        if payload.get("schema_version", DECISION_SCHEMA) != DECISION_SCHEMA:
            raise ValueError("unsupported PARALLAX decision schema")
        asset = _text(payload.get("asset"), "asset", 32).upper()
        action = _text(payload.get("action"), "action", 16).lower()
        if action not in _ALLOWED_ACTIONS:
            raise ValueError("unsupported action")
        observed_at = _text(payload.get("observed_at"), "observed_at", 80)
        regime = _text(payload.get("regime", "unknown"), "regime", 80)
        source_commit = _exact_git_sha(payload.get("source_commit"))
        context = payload.get("context", {})
        votes = payload.get("subsystem_votes", {})
        if not isinstance(context, Mapping) or not isinstance(votes, Mapping):
            raise ValueError("context and subsystem_votes must be objects")
        contract = _normalize_contract(payload.get("comparison_contract"))
        strata = _normalize_strata(payload.get("strata"), context)
        context_json = _json(dict(context), "context")
        votes_json = _json(dict(votes), "subsystem_votes")
        contract_json = _json(contract, "comparison_contract", 16384)
        strata_json = _json(strata, "strata", 8192)
        context_hash = _sha(
            "|".join(
                (
                    source_commit,
                    asset,
                    action,
                    regime,
                    observed_at,
                    context_json,
                    votes_json,
                    contract_json,
                    strata_json,
                )
            )
        )
        decision_id = str(payload.get("decision_id") or ("px-" + context_hash[:24]))
        decision_id = _text(decision_id, "decision_id", 96)

        raw_branches = payload.get("branches")
        branches = self._default_branches(action, votes) if raw_branches is None else raw_branches
        if not isinstance(branches, list) or not branches or len(branches) > 96:
            raise ValueError("branches must contain 1-96 branch specifications")

        normalized: list[tuple[str, str, str, str]] = []
        labels: set[str] = set()
        for item in branches:
            if not isinstance(item, Mapping):
                raise ValueError("branch entries must be objects")
            kind = _text(item.get("kind"), "branch.kind", 32).lower()
            label = _text(item.get("label"), "branch.label", 96).lower()
            if label in labels:
                raise ValueError("branch labels must be unique per decision")
            labels.add(label)
            params = item.get("params", {})
            if not isinstance(params, Mapping):
                raise ValueError("branch.params must be an object")
            branch_id = "pxb-" + _sha(decision_id + "|" + label)[:24]
            normalized.append((branch_id, kind, label, _json(dict(params), "branch.params", 16384)))

        if "actual" not in labels:
            raise ValueError("branches must include an 'actual' branch")

        with _LOCK, self._connect() as con:
            existing = con.execute("SELECT * FROM decisions WHERE decision_id=?", (decision_id,)).fetchone()
            if existing:
                if existing["context_hash"] != context_hash or existing["source_commit"] != source_commit:
                    raise ValueError("decision_id already exists with different immutable identity")
                return self.decision(decision_id)
            con.execute(
                """INSERT INTO decisions(
                       decision_id,observed_at,asset,action,regime,source_commit,context_hash,
                       context_json,votes_json,contract_json,strata_json,created_at
                   ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    decision_id,
                    observed_at,
                    asset,
                    action,
                    regime,
                    source_commit,
                    context_hash,
                    context_json,
                    votes_json,
                    contract_json,
                    strata_json,
                    _utc_now(),
                ),
            )
            con.executemany(
                "INSERT INTO branches(branch_id,decision_id,kind,label,params_json,status) VALUES (?,?,?,?,?,'pending')",
                [(bid, decision_id, kind, label, params) for bid, kind, label, params in normalized],
            )
        return self.decision(decision_id)

    def record_outcome(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        if not isinstance(payload, Mapping):
            raise ValueError("outcome must be an object")
        if payload.get("schema_version", OUTCOME_SCHEMA) != OUTCOME_SCHEMA:
            raise ValueError("unsupported PARALLAX outcome schema")
        decision_id = _text(payload.get("decision_id"), "decision_id", 96)
        branch_id = payload.get("branch_id")
        label = payload.get("label")
        utility = _finite(payload.get("utility"), "utility")
        metrics = payload.get("metrics", {})
        evidence = payload.get("evidence", [])
        if not isinstance(metrics, Mapping):
            raise ValueError("metrics must be an object")
        if isinstance(evidence, str):
            evidence = [evidence]
        if not isinstance(evidence, list) or len(evidence) > 32:
            raise ValueError("evidence must be a list with at most 32 items")
        metrics_json = _json(dict(metrics), "metrics", 32768)
        evidence_json = _json([_text(x, "evidence item", 700) for x in evidence], "evidence", 32768)
        observed_at = _text(payload.get("observed_at", _utc_now()), "observed_at", 80)

        with _LOCK, self._connect() as con:
            if branch_id:
                row = con.execute(
                    "SELECT * FROM branches WHERE decision_id=? AND branch_id=?",
                    (decision_id, str(branch_id)),
                ).fetchone()
            else:
                row = con.execute(
                    "SELECT * FROM branches WHERE decision_id=? AND label=?",
                    (decision_id, str(label or "").lower()),
                ).fetchone()
            if not row:
                raise ValueError("unknown PARALLAX branch")
            if row["status"] == "observed":
                prior = float(row["utility"])
                if abs(prior - utility) > 1e-12 or (row["metrics_json"] or "{}") != metrics_json:
                    raise ValueError("observed branch outcome is immutable")
                return self.decision(decision_id)
            con.execute(
                "UPDATE branches SET utility=?,metrics_json=?,evidence_json=?,observed_at=?,status='observed' WHERE branch_id=?",
                (utility, metrics_json, evidence_json, observed_at, row["branch_id"]),
            )
        return self.decision(decision_id)

    def decision(self, decision_id: str) -> dict[str, Any]:
        with _LOCK, self._connect() as con:
            row = con.execute("SELECT * FROM decisions WHERE decision_id=?", (decision_id,)).fetchone()
            if not row:
                raise ValueError("unknown PARALLAX decision")
            branches = con.execute(
                "SELECT * FROM branches WHERE decision_id=? ORDER BY rowid",
                (decision_id,),
            ).fetchall()
        contract = _normalize_contract(json.loads(row["contract_json"] or "{}"))
        strata = json.loads(row["strata_json"] or "{}")
        contract_json = _json(contract, "comparison_contract", 16384)
        strata_json = _json(strata, "strata", 8192)
        out = {
            "decision_id": row["decision_id"],
            "observed_at": row["observed_at"],
            "asset": row["asset"],
            "action": row["action"],
            "regime": row["regime"],
            "source_commit": row["source_commit"],
            "context_hash": row["context_hash"],
            "context": json.loads(row["context_json"]),
            "subsystem_votes": json.loads(row["votes_json"]),
            "comparison_contract": contract,
            "comparison_contract_hash": _sha(contract_json),
            "comparison_contract_complete": _contract_complete(contract),
            "strata": strata,
            "strata_signature": "unstratified" if not strata else _sha(strata_json)[:16],
            "branches": [],
        }
        actual = None
        observed: list[dict[str, Any]] = []
        observed_with_evidence = 0
        for b in branches:
            evidence = json.loads(b["evidence_json"] or "[]")
            item = {
                "branch_id": b["branch_id"],
                "kind": b["kind"],
                "label": b["label"],
                "params": json.loads(b["params_json"]),
                "status": b["status"],
                "utility": b["utility"],
                "metrics": json.loads(b["metrics_json"] or "{}"),
                "evidence": evidence,
                "evidence_complete": bool(_evidence_list(evidence)),
                "observed_at": b["observed_at"],
            }
            out["branches"].append(item)
            if b["status"] == "observed":
                observed.append(item)
                if item["evidence_complete"]:
                    observed_with_evidence += 1
                if b["label"] == "actual":
                    actual = item
        total = len(branches)
        coverage = len(observed) / total if total else 0.0
        evidence_coverage = observed_with_evidence / len(observed) if observed else 0.0
        if actual is not None and observed:
            best = max(observed, key=lambda x: float(x["utility"]))
            out["analysis"] = {
                "actual_utility": actual["utility"],
                "best_observed_utility": best["utility"],
                "best_observed_branch": best["label"],
                "regret": float(best["utility"]) - float(actual["utility"]),
                "observed_branch_count": len(observed),
                "observed_with_evidence_count": observed_with_evidence,
                "branch_coverage_ratio": coverage,
                "evidence_coverage_ratio": evidence_coverage,
                "actual_evidence_complete": bool(actual["evidence_complete"]),
                "complete": len(observed) == total,
            }
        else:
            out["analysis"] = {
                "complete": False,
                "observed_branch_count": len(observed),
                "observed_with_evidence_count": observed_with_evidence,
                "branch_coverage_ratio": coverage,
                "evidence_coverage_ratio": evidence_coverage,
                "actual_evidence_complete": False,
                "regret": None,
            }
        out["execution_authorized"] = False
        out["production_decision_authorized"] = False
        return out

    def _paired_rows(self) -> list[sqlite3.Row]:
        with _LOCK, self._connect() as con:
            return con.execute(
                """
                SELECT d.decision_id,d.asset,d.regime,d.source_commit,d.contract_json,d.strata_json,
                       a.utility AS actual_utility,a.evidence_json AS actual_evidence_json,
                       b.kind,b.label,b.utility AS branch_utility,b.params_json,
                       b.evidence_json AS branch_evidence_json
                FROM decisions d
                JOIN branches a ON a.decision_id=d.decision_id AND a.label='actual' AND a.status='observed'
                JOIN branches b ON b.decision_id=d.decision_id AND b.status='observed' AND b.label<>'actual'
                """
            ).fetchall()

    @staticmethod
    def _stats(values: list[float]) -> dict[str, Any]:
        n = len(values)
        if not n:
            return {
                "n": 0,
                "mean_delta": None,
                "median_delta": None,
                "std_dev": None,
                "std_error": None,
                "ci95_low": None,
                "ci95_high": None,
                "p_one_sided": None,
                "positive_fraction": None,
            }
        mean = sum(values) / n
        ordered = sorted(values)
        mid = n // 2
        median = ordered[mid] if n % 2 else (ordered[mid - 1] + ordered[mid]) / 2.0
        positive_fraction = sum(1 for x in values if x > 0) / n
        if n < 2:
            return {
                "n": n,
                "mean_delta": mean,
                "median_delta": median,
                "std_dev": None,
                "std_error": None,
                "ci95_low": None,
                "ci95_high": None,
                "p_one_sided": None,
                "positive_fraction": positive_fraction,
            }
        var = sum((x - mean) ** 2 for x in values) / (n - 1)
        std = math.sqrt(max(0.0, var))
        se = std / math.sqrt(n)
        if se <= 0:
            p = 0.0 if mean > 0 else (0.5 if mean == 0 else 1.0)
        else:
            z = mean / se
            p = 0.5 * math.erfc(z / math.sqrt(2.0))
        return {
            "n": n,
            "mean_delta": mean,
            "median_delta": median,
            "std_dev": std,
            "std_error": se,
            "ci95_low": mean - 1.96 * se,
            "ci95_high": mean + 1.96 * se,
            "p_one_sided": max(0.0, min(1.0, p)),
            "positive_fraction": positive_fraction,
        }

    @staticmethod
    def _apply_bh(items: list[dict[str, Any]]) -> None:
        by_family: dict[tuple[str, str, str, str], list[dict[str, Any]]] = {}
        for item in items:
            p = item.get("p_one_sided")
            if p is None:
                item["q_value"] = None
                continue
            family = (
                str(item["asset"]),
                str(item["regime"]),
                str(item["source_commit"]),
                str(item["comparison_contract_hash"]),
            )
            by_family.setdefault(family, []).append(item)
        for rows in by_family.values():
            ranked = sorted(rows, key=lambda x: float(x["p_one_sided"]))
            m = len(ranked)
            running = 1.0
            for rank in range(m, 0, -1):
                row = ranked[rank - 1]
                raw_q = float(row["p_one_sided"]) * m / rank
                running = min(running, raw_q)
                row["q_value"] = max(0.0, min(1.0, running))

    def _screened_hypotheses(
        self,
        min_samples: int = 5,
        max_fdr: float = 0.10,
        min_effect: float = 0.0,
    ) -> list[dict[str, Any]]:
        min_samples = max(2, min(10000, int(min_samples)))
        max_fdr = max(1e-6, min(1.0, float(max_fdr)))
        min_effect = float(min_effect)

        groups: dict[tuple[str, str, str, str, str, str], dict[str, Any]] = {}
        for row in self._paired_rows():
            contract = _normalize_contract(json.loads(row["contract_json"] or "{}"))
            contract_json = _json(contract, "comparison_contract", 16384)
            contract_hash = _sha(contract_json)
            key = (
                row["asset"],
                row["regime"],
                row["source_commit"],
                contract_hash,
                row["kind"],
                row["label"],
            )
            group = groups.setdefault(
                key,
                {
                    "asset": row["asset"],
                    "regime": row["regime"],
                    "source_commit": row["source_commit"],
                    "comparison_contract": contract,
                    "comparison_contract_hash": contract_hash,
                    "comparison_contract_complete": _contract_complete(contract),
                    "kind": row["kind"],
                    "branch_label": row["label"],
                    "branch_params": json.loads(row["params_json"] or "{}"),
                    "pair_count_total": 0,
                    "values": [],
                    "strata": {},
                },
            )
            group["pair_count_total"] += 1
            actual_evidence = _evidence_list(json.loads(row["actual_evidence_json"] or "[]"))
            branch_evidence = _evidence_list(json.loads(row["branch_evidence_json"] or "[]"))
            if not actual_evidence or not branch_evidence:
                continue
            delta = float(row["branch_utility"]) - float(row["actual_utility"])
            group["values"].append(delta)
            strata = json.loads(row["strata_json"] or "{}")
            strata_json = _json(strata, "strata", 8192)
            signature = "unstratified" if not strata else _sha(strata_json)[:16]
            bucket = group["strata"].setdefault(signature, {"signature": signature, "strata": strata, "values": []})
            bucket["values"].append(delta)

        hypotheses: list[dict[str, Any]] = []
        for group in groups.values():
            stats = self._stats(group.pop("values"))
            strata_stats = []
            for bucket in group.pop("strata").values():
                row_stats = self._stats(bucket.pop("values"))
                strata_stats.append({**bucket, **row_stats})
            strata_stats.sort(key=lambda x: (x["n"], x["mean_delta"] if x["mean_delta"] is not None else -1e99), reverse=True)
            item = {
                **group,
                **stats,
                "evidence_pair_count": stats["n"],
                "evidence_pair_coverage": (
                    stats["n"] / group["pair_count_total"] if group["pair_count_total"] else 0.0
                ),
                "strata_stats": strata_stats,
                "strata_count": len(strata_stats),
                "screening": {
                    "min_samples": min_samples,
                    "max_fdr": max_fdr,
                    "min_effect": min_effect,
                },
            }
            hypotheses.append(item)

        self._apply_bh(hypotheses)
        for item in hypotheses:
            blockers: list[str] = []
            if item["evidence_pair_count"] < min_samples:
                blockers.append("insufficient_evidence_pairs")
            if not item["comparison_contract_complete"]:
                blockers.append("comparison_contract_incomplete")
            if item["ci95_low"] is None or float(item["ci95_low"]) <= min_effect:
                blockers.append("effect_lower_bound_not_positive")
            if item.get("q_value") is None or float(item["q_value"]) > max_fdr:
                blockers.append("fdr_screen_not_cleared")
            item["screen_blockers"] = blockers
            item["candidate_eligible"] = not blockers
        hypotheses.sort(
            key=lambda x: (
                bool(x["candidate_eligible"]),
                -(float(x["q_value"]) if x.get("q_value") is not None else 1.0),
                float(x["ci95_low"]) if x.get("ci95_low") is not None else -1e99,
                float(x["mean_delta"]) if x.get("mean_delta") is not None else -1e99,
            ),
            reverse=True,
        )
        return hypotheses

    def mutation_signals(
        self,
        min_samples: int = 5,
        max_fdr: float = 0.10,
        min_effect: float = 0.0,
    ) -> list[dict[str, Any]]:
        return [
            item
            for item in self._screened_hypotheses(
                min_samples=min_samples,
                max_fdr=max_fdr,
                min_effect=min_effect,
            )
            if item["candidate_eligible"]
        ]

    def screening_report(
        self,
        min_samples: int = 5,
        max_fdr: float = 0.10,
        min_effect: float = 0.0,
    ) -> dict[str, Any]:
        hypotheses = self._screened_hypotheses(
            min_samples=min_samples,
            max_fdr=max_fdr,
            min_effect=min_effect,
        )
        blockers: dict[str, int] = {}
        for item in hypotheses:
            for reason in item["screen_blockers"]:
                blockers[reason] = blockers.get(reason, 0) + 1
        return {
            "hypotheses_total": len(hypotheses),
            "candidate_ready": sum(1 for item in hypotheses if item["candidate_eligible"]),
            "blocked": sum(1 for item in hypotheses if not item["candidate_eligible"]),
            "blocker_counts": blockers,
            "min_samples": max(2, min(10000, int(min_samples))),
            "max_fdr": max(1e-6, min(1.0, float(max_fdr))),
            "min_effect": float(min_effect),
            "hypotheses": hypotheses[:100],
            "method": {
                "paired_delta": True,
                "approximate_one_sided_normal_p": True,
                "benjamini_hochberg_within_asset_regime_revision_contract": True,
                "causal_proof": False,
            },
        }

    def _regret_summary(self, decisions: list[dict[str, Any]]) -> dict[str, Any]:
        groups: dict[tuple[str, str, str, str], dict[str, Any]] = {}
        for decision in decisions:
            regret = decision.get("analysis", {}).get("regret")
            if regret is None:
                continue
            key = (
                str(decision["asset"]),
                str(decision["regime"]),
                str(decision["source_commit"]),
                str(decision["comparison_contract_hash"]),
            )
            group = groups.setdefault(
                key,
                {
                    "asset": decision["asset"],
                    "regime": decision["regime"],
                    "source_commit": decision["source_commit"],
                    "comparison_contract_hash": decision["comparison_contract_hash"],
                    "comparison_contract": decision["comparison_contract"],
                    "values": [],
                },
            )
            group["values"].append(float(regret))
        rows = []
        for group in groups.values():
            rows.append({**{k: v for k, v in group.items() if k != "values"}, **self._stats(group["values"])})
        rows.sort(key=lambda x: (x["n"], x["mean_delta"] if x["mean_delta"] is not None else -1e99), reverse=True)
        if len(rows) == 1:
            overall = {k: rows[0].get(k) for k in ("n", "mean_delta", "median_delta", "ci95_low", "ci95_high")}
        else:
            overall = {
                "n": sum(int(row["n"]) for row in rows),
                "mean_delta": None,
                "median_delta": None,
                "ci95_low": None,
                "ci95_high": None,
            }
        return {
            **overall,
            "comparable_globally": len(rows) <= 1,
            "groups": rows,
        }

    def _ablation_attribution(self) -> list[dict[str, Any]]:
        grouped: dict[tuple[str, str, str, str, str], dict[str, Any]] = {}
        for row in self._paired_rows():
            if row["kind"] != "ablation":
                continue
            actual_evidence = _evidence_list(json.loads(row["actual_evidence_json"] or "[]"))
            branch_evidence = _evidence_list(json.loads(row["branch_evidence_json"] or "[]"))
            if not actual_evidence or not branch_evidence:
                continue
            params = json.loads(row["params_json"] or "{}")
            subsystem = str(params.get("remove_subsystem") or row["label"])
            contract = _normalize_contract(json.loads(row["contract_json"] or "{}"))
            contract_hash = _sha(_json(contract, "comparison_contract", 16384))
            key = (subsystem, row["asset"], row["regime"], row["source_commit"], contract_hash)
            group = grouped.setdefault(
                key,
                {
                    "subsystem": subsystem,
                    "asset": row["asset"],
                    "regime": row["regime"],
                    "source_commit": row["source_commit"],
                    "comparison_contract_hash": contract_hash,
                    "values": [],
                },
            )
            group["values"].append(float(row["actual_utility"]) - float(row["branch_utility"]))
        out = []
        for group in grouped.values():
            out.append({**{k: v for k, v in group.items() if k != "values"}, **self._stats(group["values"])})
        out.sort(
            key=lambda x: (
                x["n"],
                x["ci95_low"] if x["ci95_low"] is not None else -1e99,
                x["mean_delta"] if x["mean_delta"] is not None else -1e99,
            ),
            reverse=True,
        )
        return out

    def snapshot(self, limit: int = 100) -> dict[str, Any]:
        with _LOCK, self._connect() as con:
            rows = con.execute(
                "SELECT decision_id FROM decisions ORDER BY observed_at DESC LIMIT ?",
                (max(1, min(500, int(limit))),),
            ).fetchall()
            counts = con.execute(
                "SELECT COUNT(*) AS decisions,"
                "(SELECT COUNT(*) FROM branches) AS branches,"
                "(SELECT COUNT(*) FROM branches WHERE status='observed') AS observed "
                "FROM decisions"
            ).fetchone()
        decisions = [self.decision(r["decision_id"]) for r in rows]
        screening = self.screening_report()
        kind_coverage: dict[str, dict[str, int]] = {}
        observed_with_evidence = 0
        contract_ready = 0
        for decision in decisions:
            if decision["comparison_contract_complete"]:
                contract_ready += 1
            for branch in decision["branches"]:
                row = kind_coverage.setdefault(branch["kind"], {"total": 0, "observed": 0, "with_evidence": 0})
                row["total"] += 1
                if branch["status"] == "observed":
                    row["observed"] += 1
                    if branch["evidence_complete"]:
                        row["with_evidence"] += 1
                        observed_with_evidence += 1

        return {
            "schema_version": SCHEMA_VERSION,
            "counts": {
                "decisions": counts["decisions"],
                "branches": counts["branches"],
                "observed_outcomes": counts["observed"],
            },
            "coverage": {
                "observed_outcomes_with_evidence": observed_with_evidence,
                "recent_decisions_with_complete_comparison_contract": contract_ready,
                "recent_decision_count": len(decisions),
                "branch_kinds": kind_coverage,
            },
            "regret": self._regret_summary(decisions),
            "paired_ablation_attribution": self._ablation_attribution(),
            "mutation_signals": [item for item in screening["hypotheses"] if item["candidate_eligible"]],
            "screening": screening,
            "decisions": decisions,
            "authority": {
                "shadow_only": True,
                "execution_authorized": False,
                "production_decision_authorized": False,
            },
            "truth_contract": {
                "counterfactual_outcomes_are_observed_not_inferred": True,
                "ablation_attribution_is_paired_not_proof_of_causality": True,
                "unobserved_branches_are_never_scored": True,
                "candidate_signals_require_complete_comparison_contract": True,
                "candidate_signals_require_evidence_on_both_paired_paths": True,
                "candidate_signals_use_bh_fdr_screen": True,
                "regret_is_not_pooled_across_incomparable_contracts": True,
                "source_revisions_are_never_pooled": True,
            },
        }
