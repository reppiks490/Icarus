"""Deterministic, evidence-aware capability index for ICARUS.

The index is intentionally conservative. Static configuration is not proof that a
provider credential, entitlement, corpus, broker session, or live feed is healthy.
It also separates three futures truths that must never be collapsed:

* continuous runtime admission;
* non-authorizing static dated-contract candidate availability; and
* execution qualification / broker-paper authorization.

This prevents agents from inferring "works" merely because they discovered a
symbol, candidate contract code, API class, dashboard row, or secret name.
"""
from __future__ import annotations

import copy
import hashlib
import json
from typing import Any, Mapping, Optional

from icarus_futures.contracts import SPECS, STRUCTURAL_SPECS

from .assets import REGISTRY
from .futures_catalog import FUTURES_PRODUCTS

SCHEMA_VERSION = "icarus-system-index-v1"
OWNER_EXECUTION_POLICY = "live_disabled"


def _canonical_json(value: Mapping[str, Any]) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def system_index_sha256(index: Mapping[str, Any]) -> str:
    payload = copy.deepcopy(dict(index))
    integrity = payload.get("integrity")
    if isinstance(integrity, dict):
        integrity.pop("sha256", None)
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def _evidence_record(root: str, *, provider_state=None) -> dict[str, Any]:
    spec = REGISTRY[root]
    supplied = dict((provider_state or {}).get(root, {}))
    verified = supplied.get("verified_access") is True
    fresh = supplied.get("fresh") is True
    qualification = str(supplied.get("qualification") or ("verified" if verified and fresh else "configured_unverified"))
    blocker = supplied.get("blocker")
    if not (verified and fresh):
        blocker = blocker or "provider evidence has not verified current access and freshness"
    return {
        "configured": True,
        "configured_source": spec.feed,
        "provider_symbol": spec.ticker,
        "feed_mode": spec.feed_mode,
        "qualification": qualification,
        "verified_access": verified,
        "fresh": fresh,
        "evidence_id": supplied.get("evidence_id"),
        "observed_at": supplied.get("observed_at"),
        "blocker": blocker,
    }


def _corpus_record(root: str, *, corpus_state=None) -> dict[str, Any]:
    supplied = dict((corpus_state or {}).get(root, {}))
    verified = supplied.get("verified") is True
    return {
        "qualified": verified,
        "manifest": supplied.get("manifest"),
        "sha256": supplied.get("sha256"),
        "coverage": supplied.get("coverage"),
        "provenance_verified": supplied.get("provenance_verified") is True,
        "execution_authorized": False,
        "blocker": None if verified else supplied.get("blocker") or "qualified corpus evidence has not been supplied",
    }


def _brain_record(root: str, *, brain_state=None) -> dict[str, Any]:
    supplied = dict((brain_state or {}).get(root, {}))
    return {
        "evidence_registered": supplied.get("evidence_registered") is True,
        "feature_revision": supplied.get("feature_revision"),
        "regime_revision": supplied.get("regime_revision"),
        "validation_gates": list(supplied.get("validation_gates") or []),
        "unresolved_gates": list(supplied.get("unresolved_gates") or []),
        "decision_authorized": supplied.get("decision_authorized") is True,
        "execution_authorized": False,
    }


def _broker_record(root: str, *, broker_state=None) -> dict[str, Any]:
    supplied = dict((broker_state or {}).get(root, {}))
    readback = supplied.get("broker_paper_readback_verified") is True
    exact_contract = supplied.get("exact_contract_verified") is True
    reconciliation = supplied.get("reconciliation_verified") is True
    return {
        "broker": supplied.get("broker", "IBKR"),
        "paper_account_verified": supplied.get("paper_account_verified") is True,
        "exact_contract_verified": exact_contract,
        "broker_paper_readback_verified": readback,
        "reconciliation_verified": reconciliation,
        "evidence_id": supplied.get("evidence_id"),
        "blocker": supplied.get("blocker") or (
            None if readback and exact_contract and reconciliation
            else "real broker-paper contract readback/reconciliation evidence is not verified"
        ),
    }


def build_system_index(
    *,
    provider_state: Optional[Mapping[str, Mapping[str, Any]]] = None,
    corpus_state: Optional[Mapping[str, Mapping[str, Any]]] = None,
    broker_state: Optional[Mapping[str, Mapping[str, Any]]] = None,
    brain_state: Optional[Mapping[str, Mapping[str, Any]]] = None,
) -> dict[str, Any]:
    """Compile the canonical futures capability graph from runtime authorities.

    Evidence maps are explicit inputs. Their absence never upgrades a capability.
    """
    assets: dict[str, Any] = {}
    for root in sorted(FUTURES_PRODUCTS):
        product = FUTURES_PRODUCTS[root]
        runtime = REGISTRY[root]
        static_candidate = root in STRUCTURAL_SPECS
        execution_qualified = root in SPECS and product.execution_qualified
        broker = _broker_record(root, broker_state=broker_state)
        data = _evidence_record(root, provider_state=provider_state)
        corpus = _corpus_record(root, corpus_state=corpus_state)
        brain = _brain_record(root, brain_state=brain_state)
        execution_blocker = None if execution_qualified else product.execution_blocker or "execution route is not qualified"
        structural_blocker = None if static_candidate else "no static dated-contract candidate is available"
        broker_paper_tradeable = bool(
            execution_qualified
            and broker["paper_account_verified"]
            and broker["exact_contract_verified"]
            and broker["broker_paper_readback_verified"]
            and broker["reconciliation_verified"]
            and data["verified_access"]
            and data["fresh"]
        )
        assets[root] = {
            "identity": {
                "root": root,
                "name": product.name,
                "provider_symbol": product.provider_symbol,
                "tv_symbol": product.tv_symbol,
                "exchange": product.exchange,
                "asset_class": product.asset_class,
                "calendar": runtime.calendar,
                "session": runtime.session,
                "continuous_research_identity": True,
                "runtime_admitted": product.runtime_qualified,
            },
            "economics": {
                "tick_size": product.tick_size,
                "point_value": product.point_value,
                "tick_value": product.tick_value,
                "full_root": product.full_root,
                "ratio_to_full": product.ratio_to_full,
            },
            "data": data,
            "corpus": corpus,
            "brain": brain,
            "execution": {
                "static_candidate_available": static_candidate,
                "candidate_execution_root": product.execution_root,
                "broker_qualification_required": True,
                "structural_qualified": static_candidate,
                "execution_qualified": execution_qualified,
                "structural_blocker": structural_blocker,
                "execution_blocker": execution_blocker,
                "resolver_model": product.roll_model,
                "cycle": product.cycle,
                # Readiness belongs to the asset command center, which has
                # provider, risk-control, and journal evidence unavailable here.
                "simulated_paper_authorized": False,
                "broker_paper_readback_verified": broker["broker_paper_readback_verified"],
                "broker_paper_tradeable": broker_paper_tradeable,
                "broker": broker,
                "live_authorized": False,
                "live_tradeable": False,
                "owner_policy": OWNER_EXECUTION_POLICY,
            },
            "dashboard": {
                "visible": True,
                "backend_state_eligible": True,
                "static_candidate_visible": static_candidate,
                "simulated_paper_controls_eligible": False,
                "broker_paper_controls_eligible": broker_paper_tradeable,
                "live_controls_eligible": False,
            },
        }

    result: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "owner_policy": {
            "live_execution": "disabled",
            "research": "allowed",
            "replay": "allowed",
            "simulated_paper": "allowed",
            "broker_paper": "qualification_required",
        },
        "assets": assets,
        "counts": {
            "futures_roots": len(assets),
            "runtime_admitted": sum(1 for product in FUTURES_PRODUCTS.values() if product.runtime_qualified),
            "static_candidates_available": sum(
                1 for record in assets.values() if record["execution"]["static_candidate_available"]
            ),
            "structural_execution_qualified": sum(
                1 for record in assets.values() if record["execution"]["execution_qualified"]
            ),
            "broker_paper_tradeable": sum(
                1 for record in assets.values() if record["execution"]["broker_paper_tradeable"]
            ),
            "live_tradeable": 0,
        },
        "integrity": {"algorithm": "sha256"},
    }
    result["integrity"]["sha256"] = system_index_sha256(result)
    return result


def system_index_json(index: Optional[Mapping[str, Any]] = None) -> str:
    return json.dumps(index or build_system_index(), sort_keys=True, indent=2, ensure_ascii=False) + "\n"


def system_index_markdown(index: Optional[Mapping[str, Any]] = None) -> str:
    data = dict(index or build_system_index())
    lines = [
        "# ICARUS Canonical System Index",
        "",
        f"Schema: `{data['schema_version']}`",
        "",
        "Live execution: DISABLED",
        "",
        "| Root | Data | Static candidate | Execution qualified | Broker paper | Live | Blocker |",
        "|---|---|---:|---:|---:|---:|---|",
    ]
    for root in sorted(data["assets"]):
        record = data["assets"][root]
        execution = record["execution"]
        data_state = record["data"]
        blocker = execution["structural_blocker"] or data_state["blocker"] or execution["broker"]["blocker"] or "none"
        blocker = str(blocker).replace("|", "\\|")
        lines.append(
            f"| {root} | {data_state['qualification']} | "
            f"{'yes' if execution['static_candidate_available'] else 'no'} | "
            f"{'yes' if execution['execution_qualified'] else 'no'} | "
            f"{'yes' if execution['broker_paper_tradeable'] else 'no'} | no | {blocker} |"
        )
    lines.extend(["", f"Integrity SHA-256: `{data['integrity']['sha256']}`", ""])
    return "\n".join(lines)
