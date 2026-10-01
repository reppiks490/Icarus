"""PARALLAX counterfactual twin engine.

Research/shadow-only decision replay ledger. It records the decision that ICARUS
actually made plus explicitly observed alternate outcomes. It never fabricates
counterfactual returns, mutates strategy inputs, places orders, or grants
production authority.

V2 adds an explicit comparison contract, exact-code/context evidence isolation,
evidence-complete paired screening, approximate one-sided significance screening
with Benjamini-Hochberg FDR control, context-strata diagnostics, and richer
counterfactual branch families. V3 adds chronological stability diagnostics and
parameter-basin robustness so isolated lucky settings do not automatically enter
DREAMSTATE. V4 adds episode-aware effective sample sizes, autocorrelation-aware
Newey-West/HAC inference, and cross-revision contradiction diagnostics so dense
market episodes and serial dependence cannot manufacture confidence. V5 adds
distributional robustness over effective episode means so a minority of oversized
wins cannot hide a losing median, weak hit-rate, or single-episode fragility.
These are hypothesis screens, not causal proof.
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
_TEMPORAL_FOLD_COUNT = 3
_TEMPORAL_MIN_PAIRS = 9
_HAC_MIN_EFFECTIVE_PAIRS = 6
_DISTRIBUTIONAL_MIN_EFFECTIVE_PAIRS = 9
_MIN_POSITIVE_EPISODE_FRACTION = 2.0 / 3.0
_TRANSPORT_MIN_REVISIONS = 2
_PARAMETER_AXES = {
    "delay": "delay_bars",
    "stop": "stop_multiplier",
    "target": "target_multiplier",
    "size": "size_multiplier",
}
_PARAMETER_MAX_GAP = {
    "delay_bars": 2.0,
    "stop_multiplier": 0.75,
    "target_multiplier": 0.75,
    "size_multiplier": 1.0,
}
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


def _timestamp(value: Any, field: str) -> tuple[str, datetime]:
    raw = _text(value, field, 80)
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as ex:
        raise ValueError(f"{field} must be an ISO 8601 timestamp with timezone") from ex
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{field} must include a timezone")
    return raw, parsed.astimezone(timezone.utc)


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
        raw = {key: context[key] for key in _DERIVED_STRATA_KEYS if key in context and context[key] is not None}
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
        observed_at, _decision_time = _timestamp(payload.get("observed_at"), "observed_at")
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
                if existing["source_commit"] != source_commit:
                    raise ValueError("decision_id already exists with different immutable identity")
                legacy_compatible = False
                if existing["context_hash"] != context_hash:
                    legacy_hash = _sha(source_commit + "|" + asset + "|" + observed_at + "|" + context_json + "|" + votes_json)
                    legacy_compatible = (
                        existing["context_hash"] == legacy_hash
                        and existing["action"] == action
                        and existing["regime"] == regime
                        and existing["observed_at"] == observed_at
                        and not strata
                        and not _contract_complete(contract)
                    )
                    if not legacy_compatible:
                        raise ValueError("decision_id already exists with different immutable identity")
                else:
                    immutable_identity = (
                        existing["asset"],
                        existing["action"],
                        existing["regime"],
                        existing["observed_at"],
                    )
                    requested_identity = (asset, action, regime, observed_at)
                    if immutable_identity != requested_identity:
                        raise ValueError("decision_id already exists with different immutable identity")

                stored_branches = con.execute(
                    "SELECT branch_id,kind,label,params_json FROM branches WHERE decision_id=? ORDER BY rowid",
                    (decision_id,),
                ).fetchall()
                stored_plan = [
                    (row["branch_id"], row["kind"], row["label"], row["params_json"])
                    for row in stored_branches
                ]
                if not (legacy_compatible and raw_branches is None) and stored_plan != normalized:
                    raise ValueError("decision_id already exists with different immutable branch plan")
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
        observed_at, outcome_time = _timestamp(payload.get("observed_at", _utc_now()), "observed_at")

        with _LOCK, self._connect() as con:
            if branch_id:
                row = con.execute(
                    "SELECT b.*,d.observed_at AS decision_observed_at FROM branches b "
                    "JOIN decisions d ON d.decision_id=b.decision_id "
                    "WHERE b.decision_id=? AND b.branch_id=?",
                    (decision_id, str(branch_id)),
                ).fetchone()
            else:
                row = con.execute(
                    "SELECT b.*,d.observed_at AS decision_observed_at FROM branches b "
                    "JOIN decisions d ON d.decision_id=b.decision_id "
                    "WHERE b.decision_id=? AND b.label=?",
                    (decision_id, str(label or "").lower()),
                ).fetchone()
            if not row:
                raise ValueError("unknown PARALLAX branch")
            _, decision_time = _timestamp(row["decision_observed_at"], "decision.observed_at")
            if outcome_time < decision_time:
                raise ValueError("outcome observed_at cannot precede the decision")
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
                       d.context_json,d.observed_at AS decision_observed_at,
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
    def _collapse_episodes(
        samples: list[tuple[str, str, str, float]],
    ) -> tuple[list[tuple[str, str, float]], dict[str, Any]]:
        """Collapse repeated decisions from the same caller-supplied market episode."""
        episodes: dict[str, dict[str, Any]] = {}
        for observed_at, decision_id, episode_id, delta in samples:
            bucket = episodes.setdefault(
                episode_id,
                {
                    "episode_id": episode_id,
                    "observed_at": observed_at,
                    "decision_id": decision_id,
                    "values": [],
                },
            )
            current_time = _timestamp(bucket["observed_at"], "episode.observed_at")[1]
            candidate_time = _timestamp(observed_at, "episode.observed_at")[1]
            if (candidate_time, decision_id) < (current_time, str(bucket["decision_id"])):
                bucket["observed_at"] = observed_at
                bucket["decision_id"] = decision_id
            bucket["values"].append(float(delta))

        collapsed: list[tuple[str, str, float]] = []
        sizes: list[int] = []
        for bucket in episodes.values():
            values = list(bucket["values"])
            sizes.append(len(values))
            collapsed.append(
                (
                    str(bucket["observed_at"]),
                    str(bucket["decision_id"]),
                    sum(values) / len(values),
                )
            )
        collapsed.sort(key=lambda row: (_timestamp(row[0], "episode.observed_at")[1], row[1]))
        return collapsed, {
            "episode_count": len(collapsed),
            "raw_pair_count": sum(sizes),
            "clustered_pair_count": max(0, sum(sizes) - len(collapsed)),
            "largest_episode_size": max(sizes) if sizes else 0,
            "used_episode_clustering": any(size > 1 for size in sizes),
        }

    @staticmethod
    def _hac_diagnostics(values: list[float]) -> dict[str, Any]:
        """Newey-West mean uncertainty for chronologically ordered effective samples."""
        n = len(values)
        if n < _HAC_MIN_EFFECTIVE_PAIRS:
            return {
                "evaluable": False,
                "required_effective_pairs": _HAC_MIN_EFFECTIVE_PAIRS,
                "lag": None,
                "std_error": None,
                "ci95_low": None,
                "ci95_high": None,
                "p_one_sided": None,
            }
        mean = sum(values) / n
        centered = [value - mean for value in values]
        lag = min(n - 1, max(1, int(n ** (1.0 / 3.0))))
        gamma0 = sum(value * value for value in centered) / n
        long_run = gamma0
        for k in range(1, lag + 1):
            gamma = sum(centered[t] * centered[t - k] for t in range(k, n)) / n
            weight = 1.0 - (k / (lag + 1.0))
            long_run += 2.0 * weight * gamma
        variance_of_mean = max(0.0, long_run / n)
        se = math.sqrt(variance_of_mean)
        if se <= 0:
            p = 0.0 if mean > 0 else (0.5 if mean == 0 else 1.0)
        else:
            z = mean / se
            p = 0.5 * math.erfc(z / math.sqrt(2.0))
        return {
            "evaluable": True,
            "required_effective_pairs": _HAC_MIN_EFFECTIVE_PAIRS,
            "lag": lag,
            "std_error": se,
            "ci95_low": mean - 1.96 * se,
            "ci95_high": mean + 1.96 * se,
            "p_one_sided": max(0.0, min(1.0, p)),
        }

    @staticmethod
    def _distributional_robustness(values: list[float]) -> dict[str, Any]:
        """Scale-free distributional diagnostics over independent episode means."""
        n = len(values)
        if n < _DISTRIBUTIONAL_MIN_EFFECTIVE_PAIRS:
            return {
                "evaluable": False,
                "required_effective_pairs": _DISTRIBUTIONAL_MIN_EFFECTIVE_PAIRS,
                "median_delta": None,
                "positive_fraction": None,
                "minimum_positive_fraction": _MIN_POSITIVE_EPISODE_FRACTION,
                "leave_one_out_min_mean": None,
                "median_positive": None,
                "positive_fraction_ok": None,
                "single_episode_fragile": None,
                "stable": None,
            }

        ordered = sorted(float(value) for value in values)
        mid = n // 2
        median = ordered[mid] if n % 2 else (ordered[mid - 1] + ordered[mid]) / 2.0
        positive_fraction = sum(1 for value in values if value > 0.0) / n
        total = sum(values)
        leave_one_out = [
            (total - float(value)) / (n - 1)
            for value in values
        ]
        leave_one_out_min = min(leave_one_out)
        median_positive = median > 0.0
        positive_fraction_ok = positive_fraction >= _MIN_POSITIVE_EPISODE_FRACTION
        single_episode_fragile = leave_one_out_min <= 0.0
        return {
            "evaluable": True,
            "required_effective_pairs": _DISTRIBUTIONAL_MIN_EFFECTIVE_PAIRS,
            "median_delta": median,
            "positive_fraction": positive_fraction,
            "minimum_positive_fraction": _MIN_POSITIVE_EPISODE_FRACTION,
            "leave_one_out_min_mean": leave_one_out_min,
            "median_positive": median_positive,
            "positive_fraction_ok": positive_fraction_ok,
            "single_episode_fragile": single_episode_fragile,
            "stable": median_positive and positive_fraction_ok and not single_episode_fragile,
        }

    @classmethod
    def _temporal_stability(cls, samples: list[tuple[str, str, float]]) -> dict[str, Any]:
        """Chronological fold diagnostics; advisory until enough paired evidence exists."""
        n = len(samples)
        if n < _TEMPORAL_MIN_PAIRS:
            return {
                "evaluable": False,
                "required_pairs": _TEMPORAL_MIN_PAIRS,
                "fold_count": 0,
                "stable": None,
                "positive_fold_fraction": None,
                "worst_fold_mean": None,
                "folds": [],
            }

        ordered = sorted(
            samples,
            key=lambda row: (_timestamp(row[0], "decision.observed_at")[1], row[1]),
        )
        fold_count = min(_TEMPORAL_FOLD_COUNT, n)
        base = n // fold_count
        remainder = n % fold_count
        folds: list[dict[str, Any]] = []
        offset = 0
        for idx in range(fold_count):
            size = base + (1 if idx < remainder else 0)
            chunk = ordered[offset: offset + size]
            offset += size
            values = [float(value) for _, _, value in chunk]
            stats = cls._stats(values)
            folds.append({
                "index": idx,
                "start_observed_at": chunk[0][0],
                "end_observed_at": chunk[-1][0],
                **stats,
            })

        means = [float(row["mean_delta"]) for row in folds if row.get("mean_delta") is not None]
        positive = sum(1 for mean in means if mean > 0)
        stable = bool(means) and positive == len(means)
        return {
            "evaluable": True,
            "required_pairs": _TEMPORAL_MIN_PAIRS,
            "fold_count": len(folds),
            "stable": stable,
            "positive_fold_fraction": positive / len(means) if means else None,
            "worst_fold_mean": min(means) if means else None,
            "folds": folds,
        }

    @staticmethod
    def _parameter_axis(kind: str, params: Mapping[str, Any]) -> tuple[str, float, str] | None:
        key = _PARAMETER_AXES.get(str(kind))
        if not key or key not in params:
            return None
        value = params.get(key)
        if type(value) not in (int, float):
            return None
        value = float(value)
        if not math.isfinite(value):
            return None
        remainder = {str(k): v for k, v in params.items() if str(k) != key}
        signature = _sha(_json(remainder, "parameter basin remainder", 8192))
        return key, value, signature

    @staticmethod
    def _apply_bh(items: list[dict[str, Any]]) -> None:
        """Apply BH to the same p-value used by the dependence-aware screen."""
        by_family: dict[tuple[str, str, str, str], list[dict[str, Any]]] = {}

        def screen_p(row: Mapping[str, Any]) -> float | None:
            value = row.get("screen_p_one_sided")
            if value is None:
                value = row.get("p_one_sided")
            return None if value is None else float(value)

        for item in items:
            p = screen_p(item)
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
            ranked = sorted(rows, key=lambda x: float(screen_p(x)))
            m = len(ranked)
            running = 1.0
            for rank in range(m, 0, -1):
                row = ranked[rank - 1]
                p = screen_p(row)
                if p is None:
                    raise ValueError("BH family unexpectedly contains a hypothesis without a p-value")
                raw_q = p * m / rank
                running = min(running, raw_q)
                row["q_value"] = max(0.0, min(1.0, running))

    @classmethod
    def _annotate_parameter_basins(cls, items: list[dict[str, Any]], min_samples: int) -> None:
        families: dict[tuple[str, str, str, str, str, str, str], list[dict[str, Any]]] = {}
        for item in items:
            axis = cls._parameter_axis(str(item.get("kind") or ""), item.get("branch_params") or {})
            if axis is None:
                item["parameter_basin"] = {
                    "evaluable": False,
                    "axis": None,
                    "value": None,
                    "neighbor_count": 0,
                    "supporting_neighbor_count": 0,
                    "supporting_neighbor_values": [],
                    "isolated_spike": False,
                    "basin_support_count": 0,
                    "basin_width": None,
                }
                continue
            axis_name, axis_value, remainder_signature = axis
            item["_parameter_axis_value"] = axis_value
            item["_parameter_remainder_signature"] = remainder_signature
            family = (
                str(item["asset"]),
                str(item["regime"]),
                str(item["source_commit"]),
                str(item["comparison_contract_hash"]),
                str(item["kind"]),
                axis_name,
                remainder_signature,
            )
            families.setdefault(family, []).append(item)

        for family, rows in families.items():
            axis_name = family[-2]
            remainder_signature = family[-1]
            max_gap = float(_PARAMETER_MAX_GAP.get(axis_name, float("inf")))
            rows.sort(key=lambda row: float(row["_parameter_axis_value"]))
            for idx, item in enumerate(rows):
                neighbors = []
                if idx > 0:
                    left_row = rows[idx - 1]
                    left_gap = abs(float(item["_parameter_axis_value"]) - float(left_row["_parameter_axis_value"]))
                    if left_gap <= max_gap and int(left_row.get("effective_pair_count", left_row.get("evidence_pair_count")) or 0) >= min_samples:
                        neighbors.append(left_row)
                if idx + 1 < len(rows):
                    right_row = rows[idx + 1]
                    right_gap = abs(float(right_row["_parameter_axis_value"]) - float(item["_parameter_axis_value"]))
                    if right_gap <= max_gap and int(right_row.get("effective_pair_count", right_row.get("evidence_pair_count")) or 0) >= min_samples:
                        neighbors.append(right_row)
                def basin_supports(row: Mapping[str, Any]) -> bool:
                    temporal = row.get("temporal_stability") or {}
                    temporal_ok = temporal.get("evaluable") is not True or temporal.get("stable") is True
                    distributional = row.get("distributional_robustness") or {}
                    distributional_ok = (
                        distributional.get("evaluable") is not True
                        or distributional.get("stable") is True
                    )
                    return row.get("candidate_eligible") is True and temporal_ok and distributional_ok

                supporting = [row for row in neighbors if basin_supports(row)]
                family_evaluable_points = sum(
                    1 for row in rows
                    if int(row.get("effective_pair_count", row.get("evidence_pair_count")) or 0) >= min_samples
                )
                evaluable = bool(neighbors)
                local_support_missing = (
                    bool(item.get("candidate_eligible"))
                    and family_evaluable_points >= 2
                    and not neighbors
                )
                isolated = bool(item.get("candidate_eligible")) and evaluable and not supporting

                left = idx
                while left > 0:
                    candidate = rows[left - 1]
                    gap = abs(float(rows[left]["_parameter_axis_value"]) - float(candidate["_parameter_axis_value"]))
                    if gap > max_gap or not basin_supports(candidate):
                        break
                    left -= 1
                right = idx
                while right + 1 < len(rows):
                    candidate = rows[right + 1]
                    gap = abs(float(candidate["_parameter_axis_value"]) - float(rows[right]["_parameter_axis_value"]))
                    if gap > max_gap or not basin_supports(candidate):
                        break
                    right += 1
                basin_rows = rows[left:right + 1] if item.get("candidate_eligible") is True else []
                basin_values = [float(row["_parameter_axis_value"]) for row in basin_rows]
                width = (max(basin_values) - min(basin_values)) if len(basin_values) >= 2 else 0.0 if basin_values else None
                item["parameter_basin"] = {
                    "evaluable": evaluable,
                    "axis": axis_name,
                    "value": float(item["_parameter_axis_value"]),
                    "neighbor_count": len(neighbors),
                    "family_evaluable_point_count": family_evaluable_points,
                    "supporting_neighbor_count": len(supporting),
                    "supporting_neighbor_values": [float(row["_parameter_axis_value"]) for row in supporting],
                    "isolated_spike": isolated,
                    "local_support_missing": local_support_missing,
                    "basin_support_count": len(basin_rows),
                    "basin_width": width,
                    "max_neighbor_gap": max_gap,
                    "remainder_signature": remainder_signature,
                }

        for item in items:
            item.pop("_parameter_axis_value", None)
            item.pop("_parameter_remainder_signature", None)

    @staticmethod
    def _annotate_transportability(items: list[dict[str, Any]], min_samples: int) -> None:
        """Diagnose whether the same mutation survives independent ICARUS source revisions."""
        families: dict[tuple[str, str, str, str, str, str], list[dict[str, Any]]] = {}
        for item in items:
            key = (
                str(item.get("asset") or ""),
                str(item.get("regime") or ""),
                str(item.get("comparison_contract_hash") or ""),
                str(item.get("kind") or ""),
                str(item.get("branch_label") or ""),
                str(item.get("branch_params_hash") or ""),
            )
            families.setdefault(key, []).append(item)

        for rows in families.values():
            evaluable = [
                row for row in rows
                if int(row.get("effective_pair_count", row.get("evidence_pair_count")) or 0) >= min_samples
            ]
            revisions = {str(row.get("source_commit") or "") for row in evaluable}
            supporting = {
                str(row.get("source_commit") or "")
                for row in evaluable
                if row.get("robust_candidate_eligible") is True
            }
            contradictory = {
                str(row.get("source_commit") or "")
                for row in evaluable
                if row.get("screen_ci95_high") is not None
                and float(row["screen_ci95_high"]) <= 0.0
            }
            is_evaluable = len(revisions) >= _TRANSPORT_MIN_REVISIONS
            stable = is_evaluable and len(supporting) >= _TRANSPORT_MIN_REVISIONS and not contradictory
            for item in rows:
                item["transportability"] = {
                    "evaluable": is_evaluable,
                    "required_revisions": _TRANSPORT_MIN_REVISIONS,
                    "evaluable_revision_count": len(revisions),
                    "supporting_revision_count": len(supporting),
                    "contradictory_revision_count": len(contradictory),
                    "supporting_revisions": sorted(supporting),
                    "contradictory_revisions": sorted(contradictory),
                    "stable": stable,
                }

    def _screened_hypotheses(
        self,
        min_samples: int = 5,
        max_fdr: float = 0.10,
        min_effect: float = 0.0,
    ) -> list[dict[str, Any]]:
        min_samples = max(2, min(10000, int(min_samples)))
        max_fdr = max(1e-6, min(1.0, float(max_fdr)))
        min_effect = float(min_effect)
        if not math.isfinite(max_fdr) or not math.isfinite(min_effect):
            raise ValueError("screening thresholds must be finite")

        groups: dict[tuple[str, str, str, str, str, str, str], dict[str, Any]] = {}
        for row in self._paired_rows():
            contract = _normalize_contract(json.loads(row["contract_json"] or "{}"))
            contract_json = _json(contract, "comparison_contract", 16384)
            contract_hash = _sha(contract_json)
            params_json = row["params_json"] or "{}"
            params_hash = _sha(params_json)
            key = (
                row["asset"],
                row["regime"],
                row["source_commit"],
                contract_hash,
                row["kind"],
                row["label"],
                params_hash,
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
                    "branch_params": json.loads(params_json),
                    "branch_params_hash": params_hash,
                    "pair_count_total": 0,
                    "values": [],
                    "episode_samples": [],
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
            context = json.loads(row["context_json"] or "{}")
            episode_raw = context.get("episode_id") if isinstance(context, Mapping) else None
            episode_id = str(episode_raw).strip() if episode_raw is not None else str(row["decision_id"])
            if not episode_id:
                episode_id = str(row["decision_id"])
            group["episode_samples"].append(
                (str(row["decision_observed_at"]), str(row["decision_id"]), episode_id, delta)
            )
            strata = json.loads(row["strata_json"] or "{}")
            strata_json = _json(strata, "strata", 8192)
            signature = "unstratified" if not strata else _sha(strata_json)[:16]
            bucket = group["strata"].setdefault(signature, {"signature": signature, "strata": strata, "values": []})
            bucket["values"].append(delta)

        hypotheses: list[dict[str, Any]] = []
        for group in groups.values():
            raw_values = group.pop("values")
            raw_pair_count = len(raw_values)
            collapsed, dependence = self._collapse_episodes(group.pop("episode_samples"))
            effective_values = [float(value) for _, _, value in collapsed]
            stats = self._stats(effective_values)
            raw_stats = self._stats(raw_values)
            hac = self._hac_diagnostics(effective_values)
            distributional = self._distributional_robustness(effective_values)
            temporal = self._temporal_stability(collapsed)
            screen_p = hac["p_one_sided"] if hac.get("evaluable") else stats.get("p_one_sided")
            screen_low = hac["ci95_low"] if hac.get("evaluable") else stats.get("ci95_low")
            screen_high = hac["ci95_high"] if hac.get("evaluable") else stats.get("ci95_high")
            strata_stats = []
            for bucket in group.pop("strata").values():
                row_stats = self._stats(bucket.pop("values"))
                strata_stats.append({**bucket, **row_stats})
            strata_stats.sort(key=lambda x: (x["n"], x["mean_delta"] if x["mean_delta"] is not None else -1e99), reverse=True)
            item = {
                **group,
                **stats,
                "evidence_pair_count": raw_pair_count,
                "effective_pair_count": stats["n"],
                "evidence_pair_coverage": (
                    raw_pair_count / group["pair_count_total"] if group["pair_count_total"] else 0.0
                ),
                "episode_dependence": dependence,
                "raw_pair_stats": raw_stats,
                "hac_inference": hac,
                "distributional_robustness": distributional,
                "screen_p_one_sided": screen_p,
                "screen_ci95_low": screen_low,
                "screen_ci95_high": screen_high,
                "strata_stats": strata_stats,
                "strata_count": len(strata_stats),
                "temporal_stability": temporal,
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
            elif item["effective_pair_count"] < min_samples:
                blockers.append("insufficient_independent_episodes")
            if not item["comparison_contract_complete"]:
                blockers.append("comparison_contract_incomplete")
            if item["screen_ci95_low"] is None or float(item["screen_ci95_low"]) <= min_effect:
                blockers.append(
                    "dependence_adjusted_lower_bound_not_positive"
                    if (item.get("hac_inference") or {}).get("evaluable")
                    else "effect_lower_bound_not_positive"
                )
            if item.get("q_value") is None or float(item["q_value"]) > max_fdr:
                blockers.append("fdr_screen_not_cleared")
            item["screen_blockers"] = blockers
            item["candidate_eligible"] = not blockers

        self._annotate_parameter_basins(hypotheses, min_samples)
        for item in hypotheses:
            robustness_blockers: list[str] = []
            temporal = item.get("temporal_stability") or {}
            if temporal.get("evaluable") is True and temporal.get("stable") is not True:
                robustness_blockers.append("temporal_instability")
            distributional = item.get("distributional_robustness") or {}
            if distributional.get("evaluable") is True:
                if distributional.get("median_positive") is not True:
                    robustness_blockers.append("nonpositive_episode_median")
                if distributional.get("positive_fraction_ok") is not True:
                    robustness_blockers.append("low_positive_episode_fraction")
                if distributional.get("single_episode_fragile") is True:
                    robustness_blockers.append("single_episode_fragility")
            basin = item.get("parameter_basin") or {}
            if basin.get("evaluable") is True and basin.get("isolated_spike") is True:
                robustness_blockers.append("isolated_parameter_spike")
            if basin.get("local_support_missing") is True:
                robustness_blockers.append("parameter_local_support_missing")
            item["robustness_blockers"] = robustness_blockers
            item["robust_candidate_eligible"] = bool(item["candidate_eligible"]) and not robustness_blockers

        self._annotate_transportability(hypotheses, min_samples)
        for item in hypotheses:
            transport = item.get("transportability") or {}
            if transport.get("evaluable") is True and int(transport.get("contradictory_revision_count") or 0) > 0:
                item["robustness_blockers"].append("cross_revision_contradiction")
                item["robust_candidate_eligible"] = False

        hypotheses.sort(
            key=lambda x: (
                bool(x["robust_candidate_eligible"]),
                bool(x["candidate_eligible"]),
                -(float(x["q_value"]) if x.get("q_value") is not None else 1.0),
                float(x["screen_ci95_low"]) if x.get("screen_ci95_low") is not None else -1e99,
                float(x["mean_delta"]) if x.get("mean_delta") is not None else -1e99,
            ),
            reverse=True,
        )
        return hypotheses

    def hypotheses(
        self,
        min_samples: int = 5,
        max_fdr: float = 0.10,
        min_effect: float = 0.0,
    ) -> list[dict[str, Any]]:
        """Return all observed hypothesis screens, including blocked hypotheses."""
        return self._screened_hypotheses(
            min_samples=min_samples,
            max_fdr=max_fdr,
            min_effect=min_effect,
        )

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
            if item["robust_candidate_eligible"]
        ]

    def screening_report(
        self,
        min_samples: int = 5,
        max_fdr: float = 0.10,
        min_effect: float = 0.0,
        hypothesis_limit: int = 200,
    ) -> dict[str, Any]:
        hypotheses = self.hypotheses(
            min_samples=min_samples,
            max_fdr=max_fdr,
            min_effect=min_effect,
        )
        blockers: dict[str, int] = {}
        robustness_blockers: dict[str, int] = {}
        for item in hypotheses:
            for reason in item["screen_blockers"]:
                blockers[reason] = blockers.get(reason, 0) + 1
            for reason in item.get("robustness_blockers", []):
                robustness_blockers[reason] = robustness_blockers.get(reason, 0) + 1
        return {
            "robustness_version": "icarus-parallax-robustness-v3",
            "hypotheses_total": len(hypotheses),
            "candidate_ready": sum(1 for item in hypotheses if item["candidate_eligible"]),
            "robust_candidate_ready": sum(1 for item in hypotheses if item["robust_candidate_eligible"]),
            "blocked": sum(1 for item in hypotheses if not item["candidate_eligible"]),
            "robustness_blocked": sum(
                1 for item in hypotheses
                if item["candidate_eligible"] and not item["robust_candidate_eligible"]
            ),
            "blocker_counts": blockers,
            "robustness_blocker_counts": robustness_blockers,
            "min_samples": max(2, min(10000, int(min_samples))),
            "max_fdr": max(1e-6, min(1.0, float(max_fdr))),
            "min_effect": float(min_effect),
            "hypotheses": hypotheses[: max(1, min(2000, int(hypothesis_limit)))],
            "hypotheses_truncated": len(hypotheses) > max(1, min(2000, int(hypothesis_limit))),
            "method": {
                "paired_delta": True,
                "approximate_one_sided_normal_p": True,
                "newey_west_hac_for_effective_episode_means_when_evaluable": True,
                "benjamini_hochberg_uses_dependence_adjusted_p_when_evaluable": True,
                "benjamini_hochberg_within_asset_regime_revision_contract": True,
                "episode_id_context_collapses_correlated_decisions_to_one_effective_sample": True,
                "cross_revision_contradiction_screen_without_effect_pooling": True,
                "distributional_median_positive_fraction_and_leave_one_out_stability_when_nine_effective_pairs_available": True,
                "chronological_three_fold_stability_when_nine_effective_pairs_available": True,
                "adjacent_parameter_basin_screen_when_neighbors_are_evaluable": True,
                "robustness_is_hypothesis_filter_not_causal_proof": True,
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

    def status(self) -> dict[str, Any]:
        """Lightweight read-only operator status for frequent root-panel polling."""
        with _LOCK, self._connect() as con:
            counts = con.execute(
                "SELECT COUNT(*) AS decisions,"
                "(SELECT COUNT(*) FROM branches) AS branches,"
                "(SELECT COUNT(*) FROM branches WHERE status='observed') AS observed,"
                "MAX(observed_at) AS latest_observed_at "
                "FROM decisions"
            ).fetchone()
        return {
            "schema_version": "icarus-parallax-status-v1",
            "status": "ready",
            "counts": {
                "decisions": counts["decisions"],
                "branches": counts["branches"],
                "observed_outcomes": counts["observed"],
            },
            "latest_observed_at": counts["latest_observed_at"],
            "execution_authorized": False,
            "production_decision_authorized": False,
        }

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
            "robustness_version": "icarus-parallax-robustness-v3",
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
            "mutation_signals": self.mutation_signals(),
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
                "caller_supplied_episode_ids_reduce_effective_sample_size_instead_of_inflating_n": True,
                "hac_uncertainty_is_used_when_enough_effective_episode_means_exist": True,
                "cross_revision_effects_are_never_pooled_but_strong_contradictions_block_robust_readiness": True,
                "distributional_robustness_blocks_outlier_driven_or_low_breadth_episode_effects_when_evaluable": True,
                "single_episode_leave_one_out_fragility_blocks_robust_readiness_when_evaluable": True,
                "temporal_robustness_is_advisory_until_nine_effective_pairs": True,
                "evaluable_temporal_instability_blocks_robust_candidates": True,
                "evaluable_isolated_parameter_spikes_block_robust_candidates": True,
                "sampled_parameter_families_without_local_support_block_robust_candidates": True,
                "parameter_basin_support_requires_adjacent_statistical_and_temporally_coherent_candidates": True,
                "regret_is_not_pooled_across_incomparable_contracts": True,
                "source_revisions_are_never_pooled": True,
            },
        }
