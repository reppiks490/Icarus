"""Evidence-backed Overview command-center metrics for the ICARUS trader UI.

This module is observability only. It never exposes credential values, never grants
execution authority, and never treats research/provider availability as alpha.

The remote research-fabric reader consumes compact, public manifests from
reppiks490/Icarus-engine. Raw vendor payloads remain outside this repository.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import math
import os
import threading
import time
from typing import Any, Callable, Mapping
from urllib.request import Request, urlopen


REMOTE_REPOSITORY = "reppiks490/Icarus-engine"
REMOTE_REF = "main"
REMOTE_ROOT = "automation_intelligence/cl_lab"
_REMOTE_BASE = f"https://raw.githubusercontent.com/{REMOTE_REPOSITORY}/{REMOTE_REF}/{REMOTE_ROOT}"
_REMOTE_FILES = {
    "databento_primary_sweep": "databento_depth_sweep_primary.json",
    "databento_secondary_sweep": "databento_depth_sweep_secondary.json",
    "databento_third_sweep": "databento_depth_sweep_third.json",
    "databento_index": "databento_depth_corpus_index.json",
    "databento_diversifier": "databento_depth_corpus_diversifier.json",
    "fred_alfred": "fred_alfred_manifest.json",
    "external_data": "external_data_fabric.json",
}

_PROVIDER_SPECS = (
    {
        "id": "databento-primary",
        "label": "Databento #1",
        "env": ("DATABENTO_API_KEY",),
        "plane": "historical-research + optional local live adapter",
        "role": "breadth / OHLCV / primary historical lane",
    },
    {
        "id": "databento-secondary",
        "label": "Databento #2",
        "env": ("DATABENTO_API_KEY_SECONDARY",),
        "plane": "historical-research",
        "role": "equity-index MBO / MBP-10",
    },
    {
        "id": "databento-third",
        "label": "Databento #3",
        "env": ("DATABENTO_API_KEY_THIRD",),
        "plane": "historical-research",
        "role": "metals / crypto / macro depth",
    },
    {
        "id": "fred",
        "label": "FRED / ALFRED",
        "env": ("FRED_API_KEY",),
        "plane": "research-fabric",
        "role": "macro / rates / liquidity / point-in-time vintages",
    },
    {
        "id": "fmp",
        "label": "FMP",
        "env": ("FMP_API_KEY",),
        "plane": "research-fabric",
        "role": "fundamentals / calendars / market context",
    },
    {
        "id": "tiingo",
        "label": "Tiingo",
        "env": ("TIINGO_API_TOKEN",),
        "plane": "research-fabric",
        "role": "long-history equities / supplemental intraday context",
    },
    {
        "id": "eodhd",
        "label": "EODHD",
        "env": ("EODHD_API_TOKEN",),
        "plane": "research-fabric",
        "role": "equity history / supplemental market context",
    },
    {
        "id": "alpaca",
        "label": "Alpaca",
        "env": ("ALPACA_API_KEY", "ALPACA_SECRET_KEY"),
        "plane": "paper-broker bridge",
        "role": "paper execution / order lifecycle / reality-gap evidence",
    },
    {
        "id": "exa",
        "label": "Exa",
        "env": ("EXA_API_KEY",),
        "plane": "credential-only",
        "role": "external research retrieval; repository adapter not integrated yet",
    },
)

_cache_lock = threading.Lock()
_cache: dict[str, Any] = {"fetched_at": 0.0, "documents": {}, "errors": {}}


def _finite(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    out = float(value)
    return out if math.isfinite(out) else None


def _clip(value: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, float(value)))


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _default_fetch_json(url: str) -> Mapping[str, Any]:
    headers = {"User-Agent": "icarus-overview-command-center/1", "Accept": "application/json"}
    token = os.environ.get("ICARUS_GITHUB_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = Request(url, headers=headers)
    with urlopen(request, timeout=8) as response:
        raw = response.read((8 << 20) + 1)
    if len(raw) > (8 << 20):
        raise ValueError("remote research manifest exceeds 8 MiB")
    value = json.loads(raw.decode("utf-8"))
    if not isinstance(value, Mapping):
        raise ValueError("remote research manifest is not an object")
    return value


def research_fabric_snapshot(
    *,
    fetch_json: Callable[[str], Mapping[str, Any]] | None = None,
    ttl_seconds: float = 120.0,
    force: bool = False,
) -> dict[str, Any]:
    """Read compact historical/research manifests without importing raw vendor data."""
    fetch = fetch_json or _default_fetch_json
    now = time.time()
    with _cache_lock:
        cached_age = now - float(_cache.get("fetched_at") or 0.0)
        if fetch_json is None and not force and _cache.get("documents") and cached_age < max(5.0, ttl_seconds):
            docs = dict(_cache["documents"])
            errors = dict(_cache["errors"])
            fetched_at = float(_cache["fetched_at"])
        else:
            docs: dict[str, Mapping[str, Any]] = {}
            errors: dict[str, str] = {}
            for key, filename in _REMOTE_FILES.items():
                try:
                    docs[key] = fetch(f"{_REMOTE_BASE}/{filename}")
                except Exception as ex:
                    errors[key] = f"{type(ex).__name__}: {ex}"[:500]
            fetched_at = now
            if fetch_json is None:
                _cache.update(fetched_at=fetched_at, documents=dict(docs), errors=dict(errors))

    index = docs.get("databento_index") if isinstance(docs.get("databento_index"), Mapping) else {}
    diversifier = docs.get("databento_diversifier") if isinstance(docs.get("databento_diversifier"), Mapping) else {}
    sweeps = {
        "primary": docs.get("databento_primary_sweep") if isinstance(docs.get("databento_primary_sweep"), Mapping) else {},
        "secondary": docs.get("databento_secondary_sweep") if isinstance(docs.get("databento_secondary_sweep"), Mapping) else {},
        "third": docs.get("databento_third_sweep") if isinstance(docs.get("databento_third_sweep"), Mapping) else {},
    }

    accounts = []
    for account in ("primary", "secondary", "third"):
        sweep = sweeps[account]
        corpus = index if account == "secondary" else diversifier if account == "third" else {}
        held = sweep.get("held_days") if isinstance(sweep.get("held_days"), list) else []
        cached_slices = int(corpus.get("cached_slices") or 0) if corpus else 0
        lane = corpus.get("lane") if isinstance(corpus.get("lane"), Mapping) else {}
        cap = _finite(lane.get("cap_usd"))
        spent = _finite(lane.get("spent_usd"))
        sweep_cap = _finite(sweep.get("cap_usd"))
        sweep_spent = _finite(sweep.get("spent_usd"))
        evidence_present = bool(held or cached_slices or (spent and spent > 0) or (sweep_spent and sweep_spent > 0))
        manifest_present = bool(sweep or corpus)
        status_values = [str(x.get("status") or "").lower() for x in (sweep, corpus) if isinstance(x, Mapping) and x]
        degraded = any(s in {"error", "failed", "blocked"} for s in status_values)
        accounts.append({
            "account": account,
            "manifest_present": manifest_present,
            "status": "degraded" if degraded else "ok" if manifest_present else "unavailable",
            "cached_slices": cached_slices,
            "held_days": len(held),
            "lane_spent_usd": spent,
            "lane_cap_usd": cap,
            "sweep_spent_usd": sweep_spent,
            "sweep_cap_usd": sweep_cap,
            "evidence_present": evidence_present,
            "historical_only": True,
        })

    external = docs.get("external_data") if isinstance(docs.get("external_data"), Mapping) else {}
    external_providers = external.get("providers") if isinstance(external.get("providers"), Mapping) else {}
    fred = docs.get("fred_alfred") if isinstance(docs.get("fred_alfred"), Mapping) else {}
    fred_series = fred.get("series") if isinstance(fred.get("series"), Mapping) else {}
    fred_ok = sum(1 for row in fred_series.values() if isinstance(row, Mapping) and str(row.get("status") or "").lower() == "ok")

    configured = {}
    for spec in _PROVIDER_SPECS:
        names = tuple(spec["env"])
        configured[spec["id"]] = all(bool((os.environ.get(name) or "").strip()) for name in names)

    remote_status = {
        "fred": "ok" if fred_series and fred_ok == len(fred_series) else "partial" if fred_ok else "unavailable",
        "fmp": str((external_providers.get("fmp") or {}).get("status") or "unavailable").lower()
            if isinstance(external_providers.get("fmp"), Mapping) else "unavailable",
        "tiingo": str((external_providers.get("tiingo") or {}).get("status") or "unavailable").lower()
            if isinstance(external_providers.get("tiingo"), Mapping) else "unavailable",
        "eodhd": str((external_providers.get("eodhd") or {}).get("status") or "unavailable").lower()
            if isinstance(external_providers.get("eodhd"), Mapping) else "unavailable",
    }

    providers = []
    account_lookup = {row["account"]: row for row in accounts}
    for spec in _PROVIDER_SPECS:
        pid = str(spec["id"])
        research_status = "unavailable"
        if pid.startswith("databento-"):
            research_status = account_lookup.get(pid.split("-", 1)[1], {}).get("status", "unavailable")
        elif pid in remote_status:
            research_status = remote_status[pid]
        elif pid == "alpaca":
            research_status = "configured" if configured[pid] else "unconfigured"
        elif pid == "exa":
            research_status = "not_integrated" if configured[pid] else "unconfigured"
        providers.append({
            "id": pid,
            "label": spec["label"],
            "configured": configured[pid],
            "plane": spec["plane"],
            "role": spec["role"],
            "research_status": research_status,
            "secret_value_exposed": False,
        })

    return {
        "schema_version": "icarus-research-fabric-overview-v1",
        "source_repository": REMOTE_REPOSITORY,
        "source_ref": REMOTE_REF,
        "fetched_at": datetime.fromtimestamp(fetched_at, timezone.utc).isoformat().replace("+00:00", "Z"),
        "errors": errors,
        "documents_available": sorted(docs),
        "databento_accounts": accounts,
        "fred": {
            "series_total": len(fred_series),
            "series_ok": fred_ok,
            "generated_at": fred.get("generated_at"),
        },
        "external_data": {
            "generated_at": external.get("generated_at"),
            "provider_status": remote_status,
            "universe": list((external.get("summary") or {}).get("universe") or [])
                if isinstance(external.get("summary"), Mapping) else [],
        },
        "providers": providers,
        "execution_authorized": False,
        "production_decision_authorized": False,
        "raw_vendor_data_imported": False,
    }


def _gauge(label: str, score: float | None, detail: str, basis: str, evidence_count: int = 0) -> dict[str, Any]:
    if score is None:
        state = "INSUFFICIENT_EVIDENCE"
        rounded = None
    else:
        rounded = int(round(_clip(score)))
        state = (
            "ELITE" if rounded >= 90 else
            "STRONG" if rounded >= 75 else
            "DEVELOPING" if rounded >= 50 else
            "EARLY" if rounded >= 25 else
            "LOW"
        )
    return {
        "label": label,
        "score": rounded,
        "state": state,
        "detail": detail,
        "basis": basis,
        "evidence_count": int(max(0, evidence_count)),
    }


def _candidate_edge_score(candidate: Mapping[str, Any], proof_rows: list[Mapping[str, Any]]) -> tuple[float, str]:
    stage = str(candidate.get("stage") or "")
    stage_score = {
        "discovered": 20.0,
        "training": 40.0,
        "validated": 65.0,
        "qualified_shadow": 85.0,
        "rejected": 0.0,
        "retired": 0.0,
    }.get(stage, 0.0)
    validation = candidate.get("validation") if isinstance(candidate.get("validation"), Mapping) else {}
    gate_total = len(validation)
    gate_passed = sum(1 for value in validation.values() if value is True)
    gate_ratio = gate_passed / gate_total if gate_total else 0.0

    rows = [row for row in proof_rows if str(row.get("candidate_id") or "") == str(candidate.get("candidate_id") or "")]
    empirical = 0.0
    empirical_detail = "no matured proof"
    if rows:
        best = max(
            rows,
            key=lambda row: (
                bool(row.get("closed_regime_sample")),
                int(row.get("settled") or 0),
                float(row.get("success_rate") or 0.0),
            ),
        )
        coverage = _finite(best.get("outcome_coverage")) or 0.0
        success = _finite(best.get("success_rate")) or 0.0
        empirical = 10.0 * _clip(coverage * 100.0) / 100.0 + 10.0 * _clip(success * 100.0) / 100.0
        if best.get("closed_regime_sample") is True:
            empirical = min(20.0, empirical + 5.0)
        empirical_detail = f"{int(best.get('settled') or 0)} settled; success {success:.0%}; coverage {coverage:.0%}"

    score = stage_score * 0.50 + gate_ratio * 35.0 + empirical
    detail = f"{candidate.get('candidate_id') or 'candidate'} · {stage or 'unknown'} · gates {gate_passed}/{gate_total or 0} · {empirical_detail}"
    return _clip(score), detail


def command_center_snapshot(
    market: Mapping[str, Any] | None,
    audit: Mapping[str, Any] | None,
    brain: Mapping[str, Any] | None,
    research_fabric: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Build transparent, research-only gauges from already-observed evidence."""
    market = market if isinstance(market, Mapping) else {}
    audit = audit if isinstance(audit, Mapping) else {}
    brain = brain if isinstance(brain, Mapping) else {}
    fabric = research_fabric if isinstance(research_fabric, Mapping) else {}

    assets = [x for x in (market.get("assets") or []) if isinstance(x, Mapping)]
    candidates = [x for x in (brain.get("candidates") or []) if isinstance(x, Mapping)]
    proof = brain.get("performance_proof") if isinstance(brain.get("performance_proof"), Mapping) else {}
    proof_rows = [x for x in (proof.get("candidate_statistics") or []) if isinstance(x, Mapping)]
    champions = [x for x in (proof.get("regime_champions") or []) if isinstance(x, Mapping)]

    if candidates:
        scored = [_candidate_edge_score(c, proof_rows) + (c,) for c in candidates if str(c.get("stage") or "") not in {"rejected", "retired"}]
        if scored:
            best_edge = max(scored, key=lambda row: row[0])
            edge = _gauge("Edge Emergence", best_edge[0], best_edge[1],
                          "candidate stage + immutable validation gates + matured empirical proof", len(candidates))
        else:
            edge = _gauge("Edge Emergence", 0.0, "all recorded candidates are rejected or retired",
                          "candidate lifecycle", len(candidates))
    else:
        edge = _gauge("Edge Emergence", None, "no evidence-backed candidate has entered the Brain pipeline",
                      "candidate lifecycle + qualification + proof", 0)

    if proof_rows:
        champion_scores = []
        for row in proof_rows:
            coverage = _finite(row.get("outcome_coverage")) or 0.0
            success = _finite(row.get("success_rate")) or 0.0
            brier = _finite(row.get("brier_score"))
            calibration = 0.0 if brier is None else _clip((1.0 - min(1.0, brier)) * 100.0) / 100.0
            closed = 1.0 if row.get("closed_regime_sample") is True else 0.0
            score = 50.0 * closed + 20.0 * _clip(coverage * 100.0) / 100.0 + 20.0 * _clip(success * 100.0) / 100.0 + 10.0 * calibration
            champion_scores.append((score, row))
        score, row = max(champion_scores, key=lambda item: item[0])
        champ_ids = {str(x.get("shadow_champion") or "") for x in champions if x.get("shadow_champion")}
        suffix = " · empirical shadow champion" if str(row.get("candidate_id") or "") in champ_ids else ""
        champion = _gauge(
            "Champion Readiness", score,
            f"{row.get('candidate_id') or 'candidate'} · {int(row.get('settled') or 0)} settled · success {( _finite(row.get('success_rate')) or 0.0):.0%}{suffix}",
            "closed regime sample + outcome coverage + observed success + Brier quality", len(proof_rows),
        )
    else:
        champion = _gauge("Champion Readiness", None, "no matured candidate performance proof yet",
                          "performance-proof ledger", 0)

    regime_values = []
    for asset in assets:
        state = asset.get("state") if isinstance(asset.get("state"), Mapping) else {}
        value = _finite(state.get("rate_regime"))
        if value is not None:
            regime_values.append(_clip(value * 100.0))
    regime = _gauge(
        "Regime Clarity",
        sum(regime_values) / len(regime_values) if regime_values else None,
        f"{len(regime_values)}/{len(assets)} assets expose regime confidence",
        "mean active-asset RATE regime confidence", len(regime_values),
    )

    consensus_values = []
    directional_votes = 0
    for asset in assets:
        state = asset.get("state") if isinstance(asset.get("state"), Mapping) else {}
        votes = [x for x in (state.get("votes") or []) if isinstance(x, Mapping)]
        long_n = sum(1 for v in votes if bool(v.get("l")) and not bool(v.get("s")))
        short_n = sum(1 for v in votes if bool(v.get("s")) and not bool(v.get("l")))
        total = long_n + short_n
        if total:
            consensus_values.append(max(long_n, short_n) / total * 100.0)
            directional_votes += total
    consensus = _gauge(
        "Signal Consensus",
        sum(consensus_values) / len(consensus_values) if consensus_values else None,
        f"{directional_votes} directional subsystem votes across {len(consensus_values)} assets",
        "majority share of directional subsystem votes", directional_votes,
    )

    summary = audit.get("summary") if isinstance(audit.get("summary"), Mapping) else {}
    audit_score = 35.0 if str(audit.get("status") or "").lower() == "green" else 0.0
    audit_score += 20.0 if int(summary.get("current_head_failures") or 0) == 0 else 0.0
    audit_score += 15.0 if int(summary.get("unresolved") or 0) == 0 else 0.0
    good_assets = sum(1 for a in assets if not str(a.get("last_error") or ""))
    audit_score += 20.0 * (good_assets / len(assets)) if assets else 0.0
    manifest_errors = fabric.get("errors") if isinstance(fabric.get("errors"), Mapping) else {}
    audit_score += 10.0 if fabric and not manifest_errors else 5.0 if fabric else 0.0
    integrity = _gauge(
        "Data Integrity", audit_score if (audit or assets or fabric) else None,
        f"repo={audit.get('status') or 'unknown'} · head failures={int(summary.get('current_head_failures') or 0)} · runtime clean {good_assets}/{len(assets)} · manifest errors {len(manifest_errors)}",
        "repository audit + runtime feed errors + research-manifest retrieval", len(assets) + len(fabric.get("documents_available") or []),
    )

    db_accounts = [x for x in (fabric.get("databento_accounts") or []) if isinstance(x, Mapping)]
    db_scores = []
    cached_slices = 0
    held_days = 0
    for row in db_accounts:
        cached_slices += int(row.get("cached_slices") or 0)
        held_days += int(row.get("held_days") or 0)
        score = 0.0
        if row.get("manifest_present") is True:
            score += 40.0
        if str(row.get("status") or "") == "ok":
            score += 30.0
        if row.get("evidence_present") is True:
            score += 30.0
        db_scores.append(score)
    micro = _gauge(
        "Microstructure Coverage",
        sum(db_scores) / len(db_scores) if db_scores else None,
        f"{sum(1 for x in db_accounts if x.get('evidence_present'))}/{len(db_accounts)} Databento historical lanes carry evidence · {cached_slices} cached depth slices · {held_days} held sweep days",
        "three-lane manifest health + presence of reduced historical MBO/MBP evidence", cached_slices + held_days,
    )

    stage_weight = {"discovered": 25.0, "training": 50.0, "validated": 75.0, "qualified_shadow": 100.0}
    active = [c for c in candidates if str(c.get("stage") or "") in stage_weight]
    momentum_score = (sum(stage_weight[str(c.get("stage"))] for c in active) / len(active)) if active else None
    research_momentum = _gauge(
        "Research Momentum", momentum_score,
        f"{len(active)} active candidates · {sum(1 for c in active if c.get('stage') == 'qualified_shadow')} qualified-shadow",
        "mean lifecycle maturity of active evidence-backed candidates", len(active),
    )

    loops = [x for x in (audit.get("loops") or []) if isinstance(x, Mapping)]
    if loops:
        good = sum(1 for row in loops if str(row.get("status") or "").upper() in {"RUN_PERSISTED", "FINALIZATION_VERIFIED", "VERIFIED", "CLEAN"})
        sync = audit.get("loop_sync") if isinstance(audit.get("loop_sync"), Mapping) else {}
        sync_good = str(sync.get("status") or "").lower() in {"green", "bundled"}
        automation_score = (good / len(loops)) * 85.0 + (15.0 if sync_good else 0.0)
        automation_detail = f"{good}/{len(loops)} loop receipts verified · sync {sync.get('status') or 'unknown'}"
    else:
        automation_score = None
        automation_detail = "no loop receipt set available"
    automation = _gauge("Automation Health", automation_score, automation_detail,
                        "verified loop receipts + automatic synchronization state", len(loops))

    if assets:
        warm = sum(1 for a in assets if a.get("warm") is True)
        clean = sum(1 for a in assets if not str(a.get("last_error") or ""))
        fresh = sum(1 for a in assets if (_finite(a.get("poll_age")) is not None and float(a.get("poll_age")) <= 60.0))
        readiness_score = 40.0 * warm / len(assets) + 30.0 * clean / len(assets) + 30.0 * fresh / len(assets)
        execution_detail = f"warm {warm}/{len(assets)} · error-free {clean}/{len(assets)} · feed-fresh {fresh}/{len(assets)}"
    else:
        readiness_score = None
        execution_detail = "no active runtime assets"
    execution = _gauge(
        "Paper Execution Readiness", readiness_score, execution_detail,
        "runtime warm state + error state + feed freshness; does not authorize a broker", len(assets),
    )

    opportunity_values = []
    near_count = 0
    for asset in assets:
        state = asset.get("state") if isinstance(asset.get("state"), Mapping) else {}
        threshold = _finite(state.get("eff_thresh"))
        long_score = _finite(state.get("final_l"))
        short_score = _finite(state.get("final_s"))
        if threshold is None or threshold <= 0 or (long_score is None and short_score is None):
            continue
        pressure = max(long_score or 0.0, short_score or 0.0) / threshold
        if state.get("entry_allowed") is False:
            pressure *= 0.5
        pressure = _clip(pressure * 100.0)
        opportunity_values.append(pressure)
        if pressure >= 80:
            near_count += 1
    opportunity = _gauge(
        "Opportunity Pressure",
        max(opportunity_values) if opportunity_values else None,
        f"{near_count} assets at >=80% of effective entry threshold; best of {len(opportunity_values)} measurable assets",
        "nearest active long/short score to each asset's effective strategy threshold", len(opportunity_values),
    )

    gauges = [edge, champion, regime, consensus, integrity, micro, research_momentum, automation, execution, opportunity]
    return {
        "schema_version": "icarus-overview-command-center-v1",
        "generated_at": _utc_now(),
        "gauges": gauges,
        "providers": list(fabric.get("providers") or []),
        "research_fabric": {
            "source_repository": fabric.get("source_repository"),
            "source_ref": fabric.get("source_ref"),
            "fetched_at": fabric.get("fetched_at"),
            "errors": dict(fabric.get("errors") or {}),
            "databento_accounts": db_accounts,
            "fred": dict(fabric.get("fred") or {}),
            "external_data": dict(fabric.get("external_data") or {}),
        },
        "authority": {
            "research_only": True,
            "execution_authorized": False,
            "production_decision_authorized": False,
            "gauge_scores_are_diagnostics_not_trade_signals": True,
        },
    }
