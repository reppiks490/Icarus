"""DREAMSTATE policy incubator fed by PARALLAX counterfactual evidence.

DREAMSTATE turns statistically screened PARALLAX counterfactual patterns into
versioned research hypotheses. Candidates remain shadow-only until every protected
validation gate is explicitly satisfied. Even then the terminal stage is
qualified_shadow; this module has no production or broker authority.

V2 consumes PARALLAX comparison-contract/FDR evidence, isolates search families by
exact code revision and comparison contract, supports target and compound policy
hypotheses, accounts for family search budget, and retires active hypotheses when
their underlying PARALLAX screen no longer holds. V3 additionally requires
PARALLAX robustness clearance when chronological or neighboring-parameter evidence
is rich enough to evaluate it. V4 carries episode-aware effective sample size,
Newey-West/HAC uncertainty, and cross-revision transportability diagnostics into
policy contracts, search accounting, Brain mirrors, and live source revalidation.
"""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from .parallax import ParallaxStore
from .brain import record_brain_event

SCHEMA_VERSION = "icarus-dreamstate-v2"
REQUIRED_GATES = (
    "causal_time",
    "provenance",
    "oos",
    "protected_holdout",
    "multiple_testing",
    "costs_slippage_latency",
    "ablation",
    "calibration",
    "ood_drift",
    "deterministic_replay",
    "independent_verification",
)
_ALLOWED_STAGES = {"proposed", "study", "validated", "qualified_shadow", "rejected", "retired"}
_TERMINAL_REVISION_STAGES = {"rejected", "retired"}
FAMILY_TRIAL_BUDGET = 12
SOURCE_FDR_MAX = 0.10
_LOCK = threading.RLock()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


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


def _git_sha(value: Any) -> str:
    value = _text(value, "source_commit", 40).lower()
    if len(value) != 40 or any(c not in "0123456789abcdef" for c in value):
        raise ValueError("source_commit must be an exact 40-character Git SHA")
    return value


def _signal_key(signal: Mapping[str, Any]) -> tuple[str, str, str, str, str, str, str]:
    return (
        str(signal.get("asset") or ""),
        str(signal.get("regime") or ""),
        str(signal.get("source_commit") or ""),
        str(signal.get("comparison_contract_hash") or ""),
        str(signal.get("kind") or ""),
        str(signal.get("branch_label") or ""),
        str(signal.get("branch_params_hash") or ""),
    )


class DreamstateLab:
    """Durable counterfactual-to-hypothesis incubator with protected gates."""

    def __init__(self, base_dir: str | os.PathLike[str], parallax: ParallaxStore | None = None):
        self.base_dir = Path(base_dir)
        self.path = self.base_dir / "research" / "dreamstate.sqlite3"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.parallax = parallax or ParallaxStore(base_dir)
        self._init()

    def _connect(self) -> sqlite3.Connection:
        con = sqlite3.connect(str(self.path), timeout=15)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA journal_mode=WAL")
        return con

    def _init(self) -> None:
        with _LOCK, self._connect() as con:
            con.executescript(
                """
                CREATE TABLE IF NOT EXISTS candidates (
                    candidate_id TEXT PRIMARY KEY,
                    family_id TEXT NOT NULL,
                    trial_index INTEGER NOT NULL,
                    asset TEXT NOT NULL,
                    regime TEXT NOT NULL,
                    hypothesis TEXT NOT NULL,
                    mutation_json TEXT NOT NULL,
                    source_commit TEXT NOT NULL,
                    source_signal_json TEXT NOT NULL,
                    stage TEXT NOT NULL,
                    validation_json TEXT NOT NULL,
                    evidence_json TEXT NOT NULL,
                    parent_candidate_id TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_dreamstate_family ON candidates(family_id, trial_index);
                CREATE INDEX IF NOT EXISTS idx_dreamstate_stage ON candidates(stage, updated_at);
                """
            )

    @staticmethod
    def _bounded_number(value: Any, name: str, low: float, high: float) -> float:
        if type(value) not in (int, float):
            raise ValueError(f"{name} must be numeric")
        value = float(value)
        if not low <= value <= high:
            raise ValueError(f"{name} must be between {low} and {high}")
        return value

    @classmethod
    def _mutation(cls, signal: Mapping[str, Any]) -> tuple[dict[str, Any], str] | None:
        label = str(signal.get("branch_label") or "").lower()
        kind = str(signal.get("kind") or "").lower()
        params = signal.get("branch_params") if isinstance(signal.get("branch_params"), Mapping) else {}

        if kind == "opposite":
            return None

        if kind == "delay":
            value = int(params.get("delay_bars", label.rsplit("_", 1)[-1]))
            if not 0 <= value <= 20:
                raise ValueError("delay candidate is outside the bounded research envelope")
            return (
                {
                    "op": "set_execution_delay_bars",
                    "family": "execution_delay",
                    "value": value,
                    "scope": "research_candidate",
                },
                f"Test whether delaying entry by {value} bars reduces paired counterfactual regret in this evidence scope.",
            )

        if kind == "stop":
            value = cls._bounded_number(params.get("stop_multiplier", label.rsplit("_", 1)[-1]), "stop multiplier", 0.25, 4.0)
            return (
                {
                    "op": "scale_stop_distance",
                    "family": "stop_scale",
                    "value": value,
                    "scope": "research_candidate",
                },
                f"Test a {value:.2f}x stop-distance policy against the immutable comparison baseline.",
            )

        if kind == "target":
            value = cls._bounded_number(params.get("target_multiplier", label.rsplit("_", 1)[-1]), "target multiplier", 0.25, 4.0)
            return (
                {
                    "op": "scale_target_distance",
                    "family": "target_scale",
                    "value": value,
                    "scope": "research_candidate",
                },
                f"Test a {value:.2f}x target-distance policy against the immutable comparison baseline.",
            )

        if kind == "size":
            value = cls._bounded_number(params.get("size_multiplier", label.rsplit("_", 1)[-1]), "size multiplier", 0.10, 2.0)
            return (
                {
                    "op": "scale_position_size",
                    "family": "size_scale",
                    "value": value,
                    "scope": "research_candidate",
                    "risk_authority": False,
                },
                f"Test {value:.2f}x sizing only under independent risk-normalized evaluation.",
            )

        if kind == "skip" or label == "skip":
            return (
                {
                    "op": "learn_abstention_gate",
                    "family": "context_abstention",
                    "scope": "research_candidate",
                    "requires_context_clustering": True,
                },
                "Test a causal abstention gate only inside the observed context/regime scope where skipping outperformed baseline.",
            )

        if kind == "ablation" or label.startswith("without_"):
            subsystem = str(params.get("remove_subsystem") or label.removeprefix("without_")).strip().lower()
            subsystem = _text(subsystem, "ablation subsystem", 96)
            return (
                {
                    "op": "review_subsystem_weight",
                    "family": "subsystem_weight:" + subsystem,
                    "subsystem": subsystem,
                    "scope": "research_candidate",
                    "automatic_removal": False,
                },
                f"Test whether {subsystem} should be context-gated or reweighted; paired ablation alone never authorizes removal.",
            )

        if kind == "compound":
            operations: list[dict[str, Any]] = []
            if "delay_bars" in params:
                delay = int(params["delay_bars"])
                if not 0 <= delay <= 20:
                    raise ValueError("compound delay is outside the bounded research envelope")
                operations.append({"op": "set_execution_delay_bars", "value": delay})
            if "stop_multiplier" in params:
                operations.append(
                    {
                        "op": "scale_stop_distance",
                        "value": cls._bounded_number(params["stop_multiplier"], "compound stop multiplier", 0.25, 4.0),
                    }
                )
            if "target_multiplier" in params:
                operations.append(
                    {
                        "op": "scale_target_distance",
                        "value": cls._bounded_number(params["target_multiplier"], "compound target multiplier", 0.25, 4.0),
                    }
                )
            if "size_multiplier" in params:
                operations.append(
                    {
                        "op": "scale_position_size",
                        "value": cls._bounded_number(params["size_multiplier"], "compound size multiplier", 0.10, 2.0),
                        "risk_authority": False,
                    }
                )
            if len(operations) < 2:
                return None
            return (
                {
                    "op": "compound_policy",
                    "family": "compound_policy",
                    "operations": operations,
                    "scope": "research_candidate",
                    "risk_authority": False,
                },
                "Test the observed compound counterfactual as one indivisible shadow policy; do not infer the value of any component from the compound result.",
            )
        return None

    @staticmethod
    def _policy_contract(candidate: Mapping[str, Any]) -> dict[str, Any]:
        signal = candidate.get("source_signal") if isinstance(candidate.get("source_signal"), Mapping) else {}
        strata_stats = signal.get("strata_stats") if isinstance(signal.get("strata_stats"), list) else []
        observed_strata = [
            row.get("strata", {})
            for row in strata_stats
            if isinstance(row, Mapping) and isinstance(row.get("strata"), Mapping)
        ]
        return {
            "scope": {
                "asset": candidate.get("asset"),
                "regime": candidate.get("regime"),
                "source_commit": candidate.get("source_commit"),
                "comparison_contract_hash": signal.get("comparison_contract_hash"),
                "comparison_contract": signal.get("comparison_contract", {}),
                "observed_strata": observed_strata,
                "source_robustness": {
                    "robust_candidate_eligible": bool(signal.get("robust_candidate_eligible")),
                    "robustness_blockers": list(signal.get("robustness_blockers") or []),
                    "temporal_stability": signal.get("temporal_stability", {}),
                    "parameter_basin": signal.get("parameter_basin", {}),
                    "episode_dependence": signal.get("episode_dependence", {}),
                    "hac_inference": signal.get("hac_inference", {}),
                    "transportability": signal.get("transportability", {}),
                },
            },
            "mutation": candidate.get("mutation", {}),
            "baseline_fallback": {
                "type": "immutable_icarus_baseline",
                "source_commit": candidate.get("source_commit"),
            },
            "reversible": True,
            "automatic_activation": False,
            "production_decision_authorized": False,
            "execution_authorized": False,
            "broker_authority": False,
            "risk_authority": False,
        }

    def _search_accounting(self, candidate: Mapping[str, Any]) -> dict[str, Any]:
        with _LOCK, self._connect() as con:
            trials_used = int(
                con.execute("SELECT COUNT(*) FROM candidates WHERE family_id=?", (candidate["family_id"],)).fetchone()[0]
            )
        signal = candidate.get("source_signal") if isinstance(candidate.get("source_signal"), Mapping) else {}
        return {
            "family_trial_index": int(candidate["trial_index"]),
            "family_trials_used": trials_used,
            "family_trial_budget": FAMILY_TRIAL_BUDGET,
            "family_trial_budget_remaining": max(0, FAMILY_TRIAL_BUDGET - trials_used),
            "source_p_one_sided": signal.get("p_one_sided"),
            "source_q_value": signal.get("q_value"),
            "source_fdr_limit": SOURCE_FDR_MAX,
            "source_evidence_pairs": signal.get("evidence_pair_count", signal.get("n")),
            "source_effective_pairs": signal.get("effective_pair_count", signal.get("n")),
            "source_pair_coverage": signal.get("evidence_pair_coverage"),
            "source_strata_count": signal.get("strata_count", 0),
            "comparison_contract_complete": bool(signal.get("comparison_contract_complete")),
            "source_statistical_candidate_eligible": bool(signal.get("candidate_eligible")),
            "source_robust_candidate_eligible": bool(signal.get("robust_candidate_eligible")),
            "source_robustness_blockers": list(signal.get("robustness_blockers") or []),
            "source_temporal_evaluable": bool((signal.get("temporal_stability") or {}).get("evaluable")),
            "source_temporal_stable": (signal.get("temporal_stability") or {}).get("stable"),
            "source_temporal_worst_fold_mean": (signal.get("temporal_stability") or {}).get("worst_fold_mean"),
            "source_parameter_basin_evaluable": bool((signal.get("parameter_basin") or {}).get("evaluable")),
            "source_parameter_basin_support_count": (signal.get("parameter_basin") or {}).get("basin_support_count"),
            "source_parameter_basin_width": (signal.get("parameter_basin") or {}).get("basin_width"),
            "source_isolated_parameter_spike": bool((signal.get("parameter_basin") or {}).get("isolated_spike")),
            "source_parameter_local_support_missing": bool((signal.get("parameter_basin") or {}).get("local_support_missing")),
            "source_parameter_family_evaluable_points": (signal.get("parameter_basin") or {}).get("family_evaluable_point_count"),
            "source_episode_clustered_pairs": (signal.get("episode_dependence") or {}).get("clustered_pair_count"),
            "source_largest_episode_size": (signal.get("episode_dependence") or {}).get("largest_episode_size"),
            "source_hac_evaluable": bool((signal.get("hac_inference") or {}).get("evaluable")),
            "source_hac_lag": (signal.get("hac_inference") or {}).get("lag"),
            "source_hac_ci95_low": (signal.get("hac_inference") or {}).get("ci95_low"),
            "source_hac_ci95_high": (signal.get("hac_inference") or {}).get("ci95_high"),
            "source_screen_ci95_low": signal.get("screen_ci95_low"),
            "source_screen_p_one_sided": signal.get("screen_p_one_sided"),
            "source_transport_evaluable": bool((signal.get("transportability") or {}).get("evaluable")),
            "source_transport_stable": (signal.get("transportability") or {}).get("stable"),
            "source_transport_supporting_revisions": (signal.get("transportability") or {}).get("supporting_revision_count"),
            "source_transport_contradictory_revisions": (signal.get("transportability") or {}).get("contradictory_revision_count"),
        }

    def _mirror_candidate(self, candidate: Mapping[str, Any]) -> dict[str, Any]:
        stage_map = {
            "proposed": "discovered",
            "study": "training",
            "validated": "validated",
            "qualified_shadow": "qualified_shadow",
            "rejected": "rejected",
            "retired": "retired",
        }
        status_map = {
            "proposed": "unverified",
            "study": "active",
            "validated": "verified",
            "qualified_shadow": "qualified",
            "rejected": "rejected",
            "retired": "retired",
        }
        signal = candidate.get("source_signal") if isinstance(candidate.get("source_signal"), Mapping) else {}
        metrics = {
            key: signal.get(key)
            for key in (
                "n",
                "evidence_pair_count",
                "effective_pair_count",
                "evidence_pair_coverage",
                "mean_delta",
                "median_delta",
                "ci95_low",
                "ci95_high",
                "p_one_sided",
                "screen_p_one_sided",
                "screen_ci95_low",
                "screen_ci95_high",
                "q_value",
                "positive_fraction",
                "branch_label",
                "kind",
                "strata_count",
                "robust_candidate_eligible",
            )
            if key in signal
        }
        evidence = list(candidate.get("evidence") or [])
        temporal = signal.get("temporal_stability") if isinstance(signal.get("temporal_stability"), Mapping) else {}
        basin = signal.get("parameter_basin") if isinstance(signal.get("parameter_basin"), Mapping) else {}
        episode = signal.get("episode_dependence") if isinstance(signal.get("episode_dependence"), Mapping) else {}
        hac = signal.get("hac_inference") if isinstance(signal.get("hac_inference"), Mapping) else {}
        transport = signal.get("transportability") if isinstance(signal.get("transportability"), Mapping) else {}
        metrics.update({
            "temporal_stable": temporal.get("stable"),
            "temporal_worst_fold_mean": temporal.get("worst_fold_mean"),
            "parameter_basin_support_count": basin.get("basin_support_count"),
            "parameter_basin_width": basin.get("basin_width"),
            "isolated_parameter_spike": basin.get("isolated_spike"),
            "parameter_local_support_missing": basin.get("local_support_missing"),
            "parameter_family_evaluable_points": basin.get("family_evaluable_point_count"),
            "episode_clustered_pairs": episode.get("clustered_pair_count"),
            "largest_episode_size": episode.get("largest_episode_size"),
            "hac_evaluable": hac.get("evaluable"),
            "hac_lag": hac.get("lag"),
            "hac_ci95_low": hac.get("ci95_low"),
            "hac_ci95_high": hac.get("ci95_high"),
            "transport_evaluable": transport.get("evaluable"),
            "transport_stable": transport.get("stable"),
            "transport_supporting_revisions": transport.get("supporting_revision_count"),
            "transport_contradictory_revisions": transport.get("contradictory_revision_count"),
        })
        evidence.append(
            "PARALLAX paired signal "
            + str(signal.get("branch_label") or "unknown")
            + " n="
            + str(signal.get("evidence_pair_count", signal.get("n", 0)))
            + " q="
            + str(signal.get("q_value"))
            + " robust="
            + str(bool(signal.get("robust_candidate_eligible")))
        )
        return record_brain_event(
            self.base_dir,
            {
                "kind": "candidate",
                "subject": str(candidate["candidate_id"]),
                "summary": str(candidate["hypothesis"]),
                "status": status_map[str(candidate["stage"])],
                "candidate_id": str(candidate["candidate_id"]),
                "stage": stage_map[str(candidate["stage"])],
                "regimes": [str(candidate["regime"])],
                "metrics": metrics,
                "validation": dict(candidate["validation"]),
                "source_repo": "reppiks490/Icarus",
                "source_commit": str(candidate["source_commit"]),
                "evidence": evidence[-32:],
                "details": {
                    "origin": "DREAMSTATE",
                    "family_id": candidate["family_id"],
                    "trial_index": candidate["trial_index"],
                    "mutation": candidate["mutation"],
                    "policy_contract": candidate["policy_contract"],
                    "search_accounting": candidate["search_accounting"],
                    "authority": "shadow_only",
                },
            },
        )

    def _retire_decayed_sources(self, hypothesis_map: Mapping[tuple[str, str, str, str, str, str, str], Mapping[str, Any]]) -> list[str]:
        retired: list[str] = []
        with _LOCK, self._connect() as con:
            rows = con.execute(
                "SELECT candidate_id,stage,source_signal_json,evidence_json FROM candidates "
                "WHERE stage NOT IN ('rejected','retired')"
            ).fetchall()
            for row in rows:
                source = json.loads(row["source_signal_json"])
                current = hypothesis_map.get(_signal_key(source))
                if current is not None and current.get("robust_candidate_eligible") is True:
                    continue
                evidence = json.loads(row["evidence_json"])
                reason = (
                    "auto-retired: PARALLAX source signal is absent from the current screen"
                    if current is None
                    else (
                        "auto-retired: PARALLAX source signal no longer clears robustness screen: "
                        + ",".join(str(x) for x in (current.get("robustness_blockers") or current.get("screen_blockers") or []))
                    )
                )
                evidence = list(dict.fromkeys((evidence + [reason])[-128:]))
                con.execute(
                    "UPDATE candidates SET stage='retired',evidence_json=?,updated_at=? WHERE candidate_id=?",
                    (_json(evidence, "evidence"), _utc_now(), row["candidate_id"]),
                )
                retired.append(row["candidate_id"])
        return retired

    def refresh(self, min_samples: int = 5) -> dict[str, Any]:
        min_samples = max(3, min(1000, int(min_samples)))
        screening = self.parallax.screening_report(min_samples=min_samples, max_fdr=SOURCE_FDR_MAX)
        all_hypotheses = self.parallax.hypotheses(min_samples=min_samples, max_fdr=SOURCE_FDR_MAX)
        hypothesis_map = {
            _signal_key(signal): signal
            for signal in all_hypotheses
            if isinstance(signal, Mapping)
        }
        auto_retired = self._retire_decayed_sources(hypothesis_map)
        signals = [
            signal
            for signal in all_hypotheses
            if isinstance(signal, Mapping) and signal.get("robust_candidate_eligible") is True
        ]

        created: list[str] = []
        touched: list[str] = list(auto_retired)
        skipped_active = 0
        skipped_budget = 0
        skipped_stale = 0
        skipped_unmappable = 0

        with _LOCK, self._connect() as con:
            for signal in signals:
                proposal = self._mutation(signal)
                if proposal is None:
                    skipped_unmappable += 1
                    continue
                mutation, hypothesis = proposal
                asset = _text(signal.get("asset"), "asset", 32).upper()
                regime = _text(signal.get("regime"), "regime", 80)
                source_commit = _git_sha(signal.get("source_commit"))
                contract_hash = _text(signal.get("comparison_contract_hash"), "comparison_contract_hash", 64)
                family = _text(str(mutation.get("family") or mutation.get("op")), "mutation family", 160)
                family_id = "dsf-" + _sha(
                    asset
                    + "|"
                    + regime
                    + "|"
                    + source_commit
                    + "|"
                    + contract_hash
                    + "|"
                    + family
                )[:20]
                signal_json = _json(dict(signal), "source_signal", 65536)
                mutation_json = _json(mutation, "mutation", 32768)
                candidate_id = "ds-" + _sha(family_id + "|" + signal_json + "|" + mutation_json)[:24]
                exact = con.execute("SELECT candidate_id FROM candidates WHERE candidate_id=?", (candidate_id,)).fetchone()
                if exact:
                    touched.append(candidate_id)
                    continue

                history = con.execute(
                    "SELECT candidate_id,trial_index,stage,source_signal_json FROM candidates "
                    "WHERE family_id=? ORDER BY trial_index DESC",
                    (family_id,),
                ).fetchall()
                parent_candidate_id = None
                if history:
                    latest = history[0]
                    if latest["stage"] not in _TERMINAL_REVISION_STAGES:
                        touched.append(latest["candidate_id"])
                        skipped_active += 1
                        continue
                    if len(history) >= FAMILY_TRIAL_BUDGET:
                        skipped_budget += 1
                        continue
                    previous_signal = json.loads(latest["source_signal_json"])
                    previous_n = int(previous_signal.get("evidence_pair_count", previous_signal.get("n", 0)) or 0)
                    current_n = int(signal.get("evidence_pair_count", signal.get("n", 0)) or 0)
                    if current_n <= previous_n:
                        skipped_stale += 1
                        continue
                    parent_candidate_id = latest["candidate_id"]

                trial_index = len(history) + 1
                validation = {gate: None for gate in REQUIRED_GATES}
                now = _utc_now()
                con.execute(
                    """INSERT INTO candidates(candidate_id,family_id,trial_index,asset,regime,hypothesis,mutation_json,
                       source_commit,source_signal_json,stage,validation_json,evidence_json,parent_candidate_id,created_at,updated_at)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        candidate_id,
                        family_id,
                        trial_index,
                        asset,
                        regime,
                        hypothesis,
                        mutation_json,
                        source_commit,
                        signal_json,
                        "proposed",
                        _json(validation, "validation"),
                        "[]",
                        parent_candidate_id,
                        now,
                        now,
                    ),
                )
                created.append(candidate_id)
                touched.append(candidate_id)

        mirrors = [self._mirror_candidate(self.candidate(candidate_id)) for candidate_id in dict.fromkeys(touched)]
        out = self.snapshot()
        out["refresh"] = {
            "created": created,
            "auto_retired_source_decay": auto_retired,
            "signal_count": len(signals),
            "robust_signal_count": len(signals),
            "statistical_signal_count": screening.get("candidate_ready", 0),
            "screened_hypotheses": screening.get("hypotheses_total", 0),
            "screen_blockers": screening.get("blocker_counts", {}),
            "robustness_blockers": screening.get("robustness_blocker_counts", {}),
            "source_fdr_limit": SOURCE_FDR_MAX,
            "min_samples": min_samples,
            "brain_mirrors": len(mirrors),
            "skipped_active_family": skipped_active,
            "skipped_family_budget": skipped_budget,
            "skipped_stale_evidence": skipped_stale,
            "skipped_unmappable_signal": skipped_unmappable,
            "family_trial_budget": FAMILY_TRIAL_BUDGET,
        }
        return out

    def _current_source_hypothesis(self, candidate: Mapping[str, Any]) -> dict[str, Any] | None:
        source = candidate.get("source_signal") if isinstance(candidate.get("source_signal"), Mapping) else {}
        screening = source.get("screening") if isinstance(source.get("screening"), Mapping) else {}
        min_samples = max(2, min(10000, int(screening.get("min_samples", 5))))
        max_fdr = float(screening.get("max_fdr", SOURCE_FDR_MAX))
        min_effect = float(screening.get("min_effect", 0.0))
        for hypothesis in self.parallax.hypotheses(
            min_samples=min_samples,
            max_fdr=max_fdr,
            min_effect=min_effect,
        ):
            if _signal_key(hypothesis) == _signal_key(source):
                return hypothesis
        return None

    def _validate_gate_preconditions(
        self,
        candidate: Mapping[str, Any],
        updates: Mapping[str, Any],
    ) -> None:
        signal = candidate.get("source_signal") if isinstance(candidate.get("source_signal"), Mapping) else {}
        contract_complete = bool(signal.get("comparison_contract_complete"))
        q_value = signal.get("q_value")
        if updates.get("multiple_testing") is True:
            if q_value is None or float(q_value) > SOURCE_FDR_MAX:
                raise ValueError("multiple_testing gate cannot pass while the PARALLAX source FDR screen is not cleared")
            if not contract_complete:
                raise ValueError("multiple_testing gate requires a complete PARALLAX comparison contract")
        if updates.get("deterministic_replay") is True and not contract_complete:
            raise ValueError("deterministic_replay gate requires a complete PARALLAX comparison contract")
        if updates.get("costs_slippage_latency") is True:
            contract = signal.get("comparison_contract") if isinstance(signal.get("comparison_contract"), Mapping) else {}
            if not contract_complete or not str(contract.get("cost_model_id") or ""):
                raise ValueError("costs_slippage_latency gate requires a complete cost-bound comparison contract")

    def evaluate(self, candidate_id: str, payload: Mapping[str, Any]) -> dict[str, Any]:
        candidate_id = _text(candidate_id, "candidate_id", 96)
        if not isinstance(payload, Mapping):
            raise ValueError("evaluation must be an object")
        updates = payload.get("validation", {})
        if not isinstance(updates, Mapping) or not updates:
            raise ValueError("validation must be a non-empty object")
        unknown = set(updates) - set(REQUIRED_GATES)
        if unknown:
            raise ValueError("unsupported validation gates: " + ", ".join(sorted(unknown)))
        evidence = payload.get("evidence", [])
        if isinstance(evidence, str):
            evidence = [evidence]
        if not isinstance(evidence, list) or len(evidence) > 64:
            raise ValueError("evidence must be a list with at most 64 items")
        evidence = [_text(x, "evidence item", 700) for x in evidence]

        candidate = self.candidate(candidate_id)
        if candidate["stage"] in {"rejected", "retired"}:
            raise ValueError("terminal DREAMSTATE candidate cannot be requalified")

        current_source = self._current_source_hypothesis(candidate)
        if current_source is None or current_source.get("robust_candidate_eligible") is not True:
            self.retire(candidate_id, "source PARALLAX hypothesis no longer clears the current robustness screen")
            raise ValueError("source PARALLAX hypothesis no longer clears the current robustness screen")

        current_candidate = dict(candidate)
        current_candidate["source_signal"] = current_source
        self._validate_gate_preconditions(current_candidate, updates)

        with _LOCK, self._connect() as con:
            row = con.execute("SELECT * FROM candidates WHERE candidate_id=?", (candidate_id,)).fetchone()
            if not row:
                raise ValueError("unknown DREAMSTATE candidate")
            if row["stage"] in {"rejected", "retired"}:
                raise ValueError("terminal DREAMSTATE candidate cannot be requalified")
            validation = json.loads(row["validation_json"])
            for gate, value in updates.items():
                if value is not None and type(value) is not bool:
                    raise ValueError(f"validation.{gate} must be boolean or null")
                previous = validation.get(gate)
                if previous is False and value is not False:
                    raise ValueError(f"failed gate {gate} is immutable; create a new candidate revision")
                validation[gate] = value
            prior_evidence = json.loads(row["evidence_json"])
            merged_evidence = list(dict.fromkeys((prior_evidence + evidence)[-128:]))

            if any(value is False for value in validation.values()):
                stage = "rejected"
            elif all(value is True for value in validation.values()):
                stage = "qualified_shadow"
            elif all(validation.get(g) is True for g in ("causal_time", "provenance", "oos", "protected_holdout")):
                stage = "validated"
            else:
                stage = "study"

            con.execute(
                "UPDATE candidates SET stage=?,validation_json=?,evidence_json=?,updated_at=? WHERE candidate_id=?",
                (stage, _json(validation, "validation"), _json(merged_evidence, "evidence"), _utc_now(), candidate_id),
            )
        candidate = self.candidate(candidate_id)
        candidate["brain_mirror"] = self._mirror_candidate(candidate)
        return candidate

    def retire(self, candidate_id: str, reason: str) -> dict[str, Any]:
        candidate_id = _text(candidate_id, "candidate_id", 96)
        reason = _text(reason, "reason", 700)
        with _LOCK, self._connect() as con:
            row = con.execute("SELECT * FROM candidates WHERE candidate_id=?", (candidate_id,)).fetchone()
            if not row:
                raise ValueError("unknown DREAMSTATE candidate")
            evidence = json.loads(row["evidence_json"])
            evidence = list(dict.fromkeys((evidence + ["retired: " + reason])[-128:]))
            con.execute(
                "UPDATE candidates SET stage='retired',evidence_json=?,updated_at=? WHERE candidate_id=?",
                (_json(evidence, "evidence"), _utc_now(), candidate_id),
            )
        candidate = self.candidate(candidate_id)
        candidate["brain_mirror"] = self._mirror_candidate(candidate)
        return candidate

    def candidate(self, candidate_id: str) -> dict[str, Any]:
        with _LOCK, self._connect() as con:
            row = con.execute("SELECT * FROM candidates WHERE candidate_id=?", (candidate_id,)).fetchone()
        if not row:
            raise ValueError("unknown DREAMSTATE candidate")
        base = {
            "candidate_id": row["candidate_id"],
            "family_id": row["family_id"],
            "trial_index": row["trial_index"],
            "asset": row["asset"],
            "regime": row["regime"],
            "hypothesis": row["hypothesis"],
            "mutation": json.loads(row["mutation_json"]),
            "source_commit": row["source_commit"],
            "source_signal": json.loads(row["source_signal_json"]),
            "stage": row["stage"],
            "validation": json.loads(row["validation_json"]),
            "evidence": json.loads(row["evidence_json"]),
            "parent_candidate_id": row["parent_candidate_id"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "execution_authorized": False,
            "production_decision_authorized": False,
        }
        base["policy_contract"] = self._policy_contract(base)
        base["search_accounting"] = self._search_accounting(base)
        return base

    def _family_summaries(self, candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
        families: dict[str, dict[str, Any]] = {}
        for candidate in candidates:
            row = families.setdefault(
                candidate["family_id"],
                {
                    "family_id": candidate["family_id"],
                    "asset": candidate["asset"],
                    "regime": candidate["regime"],
                    "source_commit": candidate["source_commit"],
                    "comparison_contract_hash": candidate["source_signal"].get("comparison_contract_hash"),
                    "trials": 0,
                    "stages": {},
                    "latest_updated_at": "",
                    "active_candidate": None,
                },
            )
            row["trials"] += 1
            stage = candidate["stage"]
            row["stages"][stage] = row["stages"].get(stage, 0) + 1
            if candidate["updated_at"] >= row["latest_updated_at"]:
                row["latest_updated_at"] = candidate["updated_at"]
            if stage not in _TERMINAL_REVISION_STAGES:
                row["active_candidate"] = candidate["candidate_id"]
        out = []
        for row in families.values():
            row["trial_budget"] = FAMILY_TRIAL_BUDGET
            row["trial_budget_remaining"] = max(0, FAMILY_TRIAL_BUDGET - row["trials"])
            row["budget_exhausted"] = row["trials"] >= FAMILY_TRIAL_BUDGET
            out.append(row)
        out.sort(key=lambda x: (x["latest_updated_at"], x["family_id"]), reverse=True)
        return out

    def status(self) -> dict[str, Any]:
        """Lightweight read-only operator status for frequent root-panel polling."""
        with _LOCK, self._connect() as con:
            stage_rows = con.execute(
                "SELECT stage,COUNT(*) AS n FROM candidates GROUP BY stage"
            ).fetchall()
            latest = con.execute(
                "SELECT MAX(updated_at) AS latest_updated_at,COUNT(*) AS total FROM candidates"
            ).fetchone()
        stages = {stage: 0 for stage in sorted(_ALLOWED_STAGES)}
        stages.update({row["stage"]: row["n"] for row in stage_rows})
        return {
            "schema_version": "icarus-dreamstate-status-v1",
            "status": "ready",
            "candidate_count": latest["total"],
            "latest_updated_at": latest["latest_updated_at"],
            "stages": stages,
            "execution_authorized": False,
            "production_decision_authorized": False,
        }

    def snapshot(self, limit: int = 200) -> dict[str, Any]:
        with _LOCK, self._connect() as con:
            rows = con.execute(
                "SELECT candidate_id FROM candidates ORDER BY updated_at DESC LIMIT ?",
                (max(1, min(1000, int(limit))),),
            ).fetchall()
            stage_rows = con.execute("SELECT stage,COUNT(*) AS n FROM candidates GROUP BY stage").fetchall()
        candidates = [self.candidate(row["candidate_id"]) for row in rows]
        stages = {stage: 0 for stage in sorted(_ALLOWED_STAGES)}
        stages.update({row["stage"]: row["n"] for row in stage_rows})
        families = self._family_summaries(candidates)
        return {
            "schema_version": SCHEMA_VERSION,
            "robustness_version": "icarus-dreamstate-robustness-v2",
            "stages": stages,
            "candidates": candidates,
            "families": families,
            "search": {
                "family_count": len(families),
                "active_family_count": sum(1 for row in families if row["active_candidate"]),
                "budget_exhausted_family_count": sum(1 for row in families if row["budget_exhausted"]),
                "family_trial_budget": FAMILY_TRIAL_BUDGET,
                "source_fdr_limit": SOURCE_FDR_MAX,
            },
            "required_gates": list(REQUIRED_GATES),
            "family_trial_budget": FAMILY_TRIAL_BUDGET,
            "authority": {
                "maximum_stage": "qualified_shadow",
                "automatic_production_promotion": False,
                "execution_authorized": False,
                "production_decision_authorized": False,
            },
            "truth_contract": {
                "counterfactual_signal_is_hypothesis_generation_only": True,
                "source_signal_must_clear_parallax_fdr_and_comparison_contract_screen": True,
                "source_signal_must_clear_parallax_robustness_when_evaluable": True,
                "temporal_instability_can_retire_shadow_candidates": True,
                "isolated_parameter_spikes_can_retire_shadow_candidates": True,
                "episode_clustering_reduces_effective_source_sample_size": True,
                "hac_dependence_adjustment_can_block_shadow_candidates": True,
                "cross_revision_contradiction_can_retire_shadow_candidates": True,
                "transportability_never_pools_effect_sizes_across_code_revisions": True,
                "multiple_testing_gate_required": True,
                "independent_verification_required": True,
                "failed_gate_requires_new_candidate_revision": True,
                "one_active_candidate_per_family": True,
                "family_trial_budget_enforced": True,
                "families_are_isolated_by_source_revision_and_comparison_contract": True,
                "source_signal_decay_can_retire_shadow_candidates": True,
                "opposite_side_counterfactual_never_auto_inverts_policy": True,
            },
        }
