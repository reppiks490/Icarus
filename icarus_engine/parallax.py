"""PARALLAX counterfactual twin engine.

Research/shadow-only decision replay ledger. It records the decision that ICARUS
actually made plus explicitly observed alternate outcomes. It never fabricates
counterfactual returns, mutates strategy inputs, places orders, or grants
production authority.
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

SCHEMA_VERSION = "icarus-parallax-v1"
DECISION_SCHEMA = "icarus-parallax-decision-v1"
OUTCOME_SCHEMA = "icarus-parallax-outcome-v1"
_ALLOWED_ACTIONS = {"long", "short", "flat", "abstain"}
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

    @staticmethod
    def _default_branches(action: str, votes: Mapping[str, Any]) -> list[dict[str, Any]]:
        branches = [
            {"kind": "actual", "label": "actual", "params": {"action": action}},
            {"kind": "skip", "label": "skip", "params": {"action": "abstain"}},
            {"kind": "opposite", "label": "opposite", "params": {"action": "short" if action == "long" else "long" if action == "short" else action}},
        ]
        for bars in (1, 2, 3, 5):
            branches.append({"kind": "delay", "label": f"delay_{bars}", "params": {"delay_bars": bars}})
        for mult in (0.75, 1.25, 1.50):
            branches.append({"kind": "stop", "label": f"stop_{mult:.2f}", "params": {"stop_multiplier": mult}})
        for mult in (0.50, 1.50):
            branches.append({"kind": "size", "label": f"size_{mult:.2f}", "params": {"size_multiplier": mult}})
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
        regime = _text(payload.get("regime", "unknown"), "regime", 120)
        source_commit = _exact_git_sha(payload.get("source_commit"))
        context = payload.get("context", {})
        votes = payload.get("subsystem_votes", {})
        if not isinstance(context, Mapping) or not isinstance(votes, Mapping):
            raise ValueError("context and subsystem_votes must be objects")
        context_json = _json(dict(context), "context")
        votes_json = _json(dict(votes), "subsystem_votes")
        context_hash = _sha(asset + "|" + observed_at + "|" + context_json + "|" + votes_json)
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
                       decision_id,observed_at,asset,action,regime,source_commit,context_hash,context_json,votes_json,created_at
                   ) VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (decision_id, observed_at, asset, action, regime, source_commit, context_hash, context_json, votes_json, _utc_now()),
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
                row = con.execute("SELECT * FROM branches WHERE decision_id=? AND branch_id=?", (decision_id, str(branch_id))).fetchone()
            else:
                row = con.execute("SELECT * FROM branches WHERE decision_id=? AND label=?", (decision_id, str(label or "").lower())).fetchone()
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
            branches = con.execute("SELECT * FROM branches WHERE decision_id=? ORDER BY rowid", (decision_id,)).fetchall()
        out = {
            "decision_id": row["decision_id"], "observed_at": row["observed_at"], "asset": row["asset"],
            "action": row["action"], "regime": row["regime"], "source_commit": row["source_commit"],
            "context_hash": row["context_hash"], "context": json.loads(row["context_json"]),
            "subsystem_votes": json.loads(row["votes_json"]), "branches": [],
        }
        actual = None
        observed = []
        for b in branches:
            item = {
                "branch_id": b["branch_id"], "kind": b["kind"], "label": b["label"],
                "params": json.loads(b["params_json"]), "status": b["status"], "utility": b["utility"],
                "metrics": json.loads(b["metrics_json"] or "{}"), "evidence": json.loads(b["evidence_json"] or "[]"),
                "observed_at": b["observed_at"],
            }
            out["branches"].append(item)
            if b["status"] == "observed":
                observed.append(item)
                if b["label"] == "actual":
                    actual = item
        if actual is not None and observed:
            best = max(observed, key=lambda x: float(x["utility"]))
            out["analysis"] = {
                "actual_utility": actual["utility"],
                "best_observed_utility": best["utility"],
                "best_observed_branch": best["label"],
                "regret": float(best["utility"]) - float(actual["utility"]),
                "observed_branch_count": len(observed),
                "complete": len(observed) == len(branches),
            }
        else:
            out["analysis"] = {"complete": False, "observed_branch_count": len(observed), "regret": None}
        out["execution_authorized"] = False
        out["production_decision_authorized"] = False
        return out

    def _paired_rows(self) -> list[sqlite3.Row]:
        with _LOCK, self._connect() as con:
            return con.execute(
                """
                SELECT d.decision_id,d.asset,d.regime,d.source_commit,
                       a.utility AS actual_utility,b.kind,b.label,b.utility AS branch_utility,b.params_json
                FROM decisions d
                JOIN branches a ON a.decision_id=d.decision_id AND a.label='actual' AND a.status='observed'
                JOIN branches b ON b.decision_id=d.decision_id AND b.status='observed' AND b.label<>'actual'
                """
            ).fetchall()

    @staticmethod
    def _stats(values: list[float]) -> dict[str, Any]:
        n = len(values)
        if not n:
            return {"n": 0, "mean_delta": None, "ci95_low": None, "ci95_high": None}
        mean = sum(values) / n
        if n < 2:
            return {"n": n, "mean_delta": mean, "ci95_low": None, "ci95_high": None}
        var = sum((x - mean) ** 2 for x in values) / (n - 1)
        se = math.sqrt(var / n)
        return {"n": n, "mean_delta": mean, "ci95_low": mean - 1.96 * se, "ci95_high": mean + 1.96 * se}

    def mutation_signals(self, min_samples: int = 5) -> list[dict[str, Any]]:
        grouped: dict[tuple[str, str, str], list[float]] = {}
        commits: dict[tuple[str, str, str], str] = {}
        for row in self._paired_rows():
            key = (row["asset"], row["regime"], row["kind"], row["label"])
            grouped.setdefault(key, []).append(float(row["branch_utility"]) - float(row["actual_utility"]))
            commits[key] = row["source_commit"]
        signals = []
        for (asset, regime, kind, label), values in grouped.items():
            stats = self._stats(values)
            if stats["n"] < min_samples or stats["ci95_low"] is None or stats["ci95_low"] <= 0:
                continue
            signals.append({
                "asset": asset, "regime": regime, "branch_label": label, "kind": kind,
                "source_commit": commits[(asset, regime, kind, label)], **stats,
            })
        return sorted(signals, key=lambda x: (x["ci95_low"], x["mean_delta"]), reverse=True)

    def snapshot(self, limit: int = 100) -> dict[str, Any]:
        with _LOCK, self._connect() as con:
            rows = con.execute("SELECT decision_id FROM decisions ORDER BY observed_at DESC LIMIT ?", (max(1, min(500, int(limit))),)).fetchall()
            counts = con.execute(
                "SELECT COUNT(*) AS decisions,(SELECT COUNT(*) FROM branches) AS branches,(SELECT COUNT(*) FROM branches WHERE status='observed') AS observed FROM decisions"
            ).fetchone()
        decisions = [self.decision(r["decision_id"]) for r in rows]
        complete = [d for d in decisions if d["analysis"].get("actual_utility") is not None]
        regrets = [float(d["analysis"]["regret"]) for d in complete if d["analysis"].get("regret") is not None]
        ablations: dict[str, list[float]] = {}
        for d in complete:
            actual = d["analysis"].get("actual_utility")
            for b in d["branches"]:
                if b["kind"] == "ablation" and b["status"] == "observed":
                    subsystem = str(b["params"].get("remove_subsystem") or b["label"])
                    ablations.setdefault(subsystem, []).append(float(actual) - float(b["utility"]))
        attribution = [{"subsystem": k, **self._stats(v)} for k, v in ablations.items()]
        attribution.sort(key=lambda x: (x["mean_delta"] if x["mean_delta"] is not None else -1e99), reverse=True)
        return {
            "schema_version": SCHEMA_VERSION,
            "counts": {"decisions": counts["decisions"], "branches": counts["branches"], "observed_outcomes": counts["observed"]},
            "regret": self._stats(regrets),
            "paired_ablation_attribution": attribution,
            "mutation_signals": self.mutation_signals(),
            "decisions": decisions,
            "authority": {"shadow_only": True, "execution_authorized": False, "production_decision_authorized": False},
            "truth_contract": {
                "counterfactual_outcomes_are_observed_not_inferred": True,
                "ablation_attribution_is_paired_not_proof_of_causality": True,
                "unobserved_branches_are_never_scored": True,
            },
        }
