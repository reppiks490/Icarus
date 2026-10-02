"""ICARUS Unified Intelligence Spine.

This module is the composition boundary for heterogeneous ICARUS cognition.
It preserves source identity, causal availability, disagreement, and evidence
ancestry while measuring *structural* redundancy between contributors.

The spine is research/shadow infrastructure only.  It cannot authorize a
production decision or broker action, and it deliberately does not claim that
structural novelty is predictive information gain.  Predictive promotion
remains downstream of ICARUS protected validation.
"""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping

SCHEMA_VERSION = "icarus-unified-intelligence-v1"

EVIDENCE_CLASSES = {
    "observed",
    "derived",
    "reconstructed",
    "inferred",
    "unavailable",
}
SOURCE_KINDS = {
    "native",
    "foreign_lens",
    "experiment",
    "human",
}


def _finite(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a finite number")
    out = float(value)
    if not math.isfinite(out):
        raise ValueError(f"{name} must be a finite number")
    return out


def _text(value: Any, name: str, limit: int = 240) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{name} must be a string")
    out = value.strip()
    if not out:
        raise ValueError(f"{name} is required")
    if len(out) > limit:
        raise ValueError(f"{name} exceeds {limit} characters")
    return out


def _parse_time(value: str, name: str) -> datetime:
    text = _text(value, name, 80)
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError as ex:
        raise ValueError(f"{name} must be ISO-8601") from ex
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise ValueError(f"{name} must include a timezone")
    return dt.astimezone(timezone.utc)


def _canonical_json(value: Any, name: str, limit: int = 32768) -> Any:
    try:
        raw = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError) as ex:
        raise ValueError(f"{name} must be finite JSON") from ex
    if len(raw.encode("utf-8")) > limit:
        raise ValueError(f"{name} exceeds {limit} bytes")
    return value


@dataclass(frozen=True)
class IntelligenceClaim:
    """One source-scoped claim about one canonical market/research semantic."""

    source: str
    source_kind: str
    semantic_key: str
    stance: float
    confidence: float
    evidence_class: str
    observed_at: str
    received_at: str
    regime: str = "*"
    horizon_seconds: int = 0
    lineage: tuple[str, ...] = ()
    falsifiers: tuple[str, ...] = ()
    details: Mapping[str, Any] = field(default_factory=dict)

    def normalized(self) -> dict[str, Any]:
        source = _text(self.source, "source", 160)
        source_kind = _text(self.source_kind, "source_kind", 40).lower()
        if source_kind not in SOURCE_KINDS:
            raise ValueError("unsupported source_kind")
        semantic_key = _text(self.semantic_key, "semantic_key", 240)
        regime = _text(self.regime, "regime", 120)
        stance = _finite(self.stance, "stance")
        confidence = _finite(self.confidence, "confidence")
        if not -1.0 <= stance <= 1.0:
            raise ValueError("stance must be in [-1, 1]")
        if not 0.0 <= confidence <= 1.0:
            raise ValueError("confidence must be in [0, 1]")
        evidence_class = _text(self.evidence_class, "evidence_class", 40).lower()
        if evidence_class not in EVIDENCE_CLASSES:
            raise ValueError("unsupported evidence_class")
        if evidence_class == "unavailable" and confidence != 0.0:
            raise ValueError("unavailable evidence must have zero confidence")
        if isinstance(self.horizon_seconds, bool) or not isinstance(self.horizon_seconds, int):
            raise ValueError("horizon_seconds must be an integer")
        if self.horizon_seconds < 0:
            raise ValueError("horizon_seconds must be non-negative")

        observed = _parse_time(self.observed_at, "observed_at")
        received = _parse_time(self.received_at, "received_at")
        if received < observed:
            raise ValueError("received_at cannot precede observed_at")

        lineage = tuple(sorted({_text(x, "lineage item", 240) for x in self.lineage}))
        falsifiers = tuple(sorted({_text(x, "falsifier", 500) for x in self.falsifiers}))
        details = _canonical_json(dict(self.details), "details")

        return {
            "schema_version": SCHEMA_VERSION,
            "source": source,
            "source_kind": source_kind,
            "semantic_key": semantic_key,
            "stance": stance,
            "confidence": confidence,
            "evidence_class": evidence_class,
            "observed_at": observed.isoformat().replace("+00:00", "Z"),
            "received_at": received.isoformat().replace("+00:00", "Z"),
            "regime": regime,
            "horizon_seconds": self.horizon_seconds,
            "lineage": list(lineage),
            "falsifiers": list(falsifiers),
            "details": details,
            "execution_authorized": False,
            "production_decision_authorized": False,
        }


def _claim_id(claim: Mapping[str, Any]) -> str:
    raw = json.dumps(dict(claim), sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _lineage_family(claim: Mapping[str, Any]) -> str:
    lineage = claim.get("lineage")
    if isinstance(lineage, list) and lineage:
        raw = json.dumps(sorted(str(x) for x in lineage), separators=(",", ":")).encode("utf-8")
        return "lineage:" + hashlib.sha256(raw).hexdigest()
    return "source:" + str(claim.get("source") or "")


def _semantic_group(claim: Mapping[str, Any]) -> tuple[str, str, int]:
    return (
        str(claim.get("semantic_key") or ""),
        str(claim.get("regime") or "*"),
        int(claim.get("horizon_seconds") or 0),
    )


class UnifiedIntelligenceSpine:
    """In-memory deterministic composition plane for ICARUS research cognition."""

    def __init__(self) -> None:
        self._claims: dict[str, dict[str, Any]] = {}

    def ingest(self, claim: IntelligenceClaim | Mapping[str, Any]) -> dict[str, Any]:
        if isinstance(claim, IntelligenceClaim):
            normalized = claim.normalized()
        elif isinstance(claim, Mapping):
            normalized = IntelligenceClaim(
                source=claim.get("source"),
                source_kind=claim.get("source_kind"),
                semantic_key=claim.get("semantic_key"),
                stance=claim.get("stance"),
                confidence=claim.get("confidence"),
                evidence_class=claim.get("evidence_class"),
                observed_at=claim.get("observed_at"),
                received_at=claim.get("received_at"),
                regime=claim.get("regime", "*"),
                horizon_seconds=claim.get("horizon_seconds", 0),
                lineage=tuple(claim.get("lineage", ()) or ()),
                falsifiers=tuple(claim.get("falsifiers", ()) or ()),
                details=claim.get("details", {}) or {},
            ).normalized()
        else:
            raise ValueError("claim must be IntelligenceClaim or mapping")

        cid = _claim_id(normalized)
        idempotent = cid in self._claims
        self._claims.setdefault(cid, normalized)
        return {
            "claim_id": cid,
            "idempotent": idempotent,
            "execution_authorized": False,
            "production_decision_authorized": False,
        }

    def ingest_many(self, claims: Iterable[IntelligenceClaim | Mapping[str, Any]]) -> list[dict[str, Any]]:
        return [self.ingest(claim) for claim in claims]

    def _available(self, as_of: str | None) -> list[dict[str, Any]]:
        claims = list(self._claims.values())
        if as_of is None:
            return claims
        boundary = _parse_time(as_of, "as_of")
        out = []
        for claim in claims:
            observed = _parse_time(str(claim["observed_at"]), "observed_at")
            received = _parse_time(str(claim["received_at"]), "received_at")
            if observed <= boundary and received <= boundary:
                out.append(claim)
        return out

    @staticmethod
    def _consensus(rows: list[dict[str, Any]]) -> dict[str, Any]:
        # Shared ancestry contributes at most once: keep the highest-confidence
        # representative in each lineage family.
        by_family: dict[str, dict[str, Any]] = {}
        for row in rows:
            family = _lineage_family(row)
            current = by_family.get(family)
            if current is None or float(row["confidence"]) > float(current["confidence"]):
                by_family[family] = row

        independent = list(by_family.values())
        weighted = [(float(row["stance"]), float(row["confidence"])) for row in independent if float(row["confidence"]) > 0.0]
        total_weight = sum(weight for _stance, weight in weighted)
        consensus = (
            sum(stance * weight for stance, weight in weighted) / total_weight
            if total_weight > 0.0
            else None
        )
        disagreement = (
            sum(abs(stance - consensus) * weight for stance, weight in weighted) / total_weight
            if consensus is not None and total_weight > 0.0
            else None
        )
        positive = any(float(row["stance"]) > 0.0 and float(row["confidence"]) > 0.0 for row in independent)
        negative = any(float(row["stance"]) < 0.0 and float(row["confidence"]) > 0.0 for row in independent)

        return {
            "consensus_stance": consensus,
            "weighted_disagreement": disagreement,
            "raw_claim_count": len(rows),
            "effective_independent_families": len(independent),
            "shared_ancestry_discounted": len(rows) - len(independent),
            "directional_conflict": positive and negative,
            "sources": sorted({str(row["source"]) for row in rows}),
            "evidence_classes": sorted({str(row["evidence_class"]) for row in rows}),
        }

    @staticmethod
    def _source_reports(claims: list[dict[str, Any]]) -> list[dict[str, Any]]:
        semantics_by_source: dict[str, set[tuple[str, str, int]]] = {}
        for claim in claims:
            semantics_by_source.setdefault(str(claim["source"]), set()).add(_semantic_group(claim))

        all_sources = sorted(semantics_by_source)
        reports = []
        for source in all_sources:
            own = semantics_by_source[source]
            others: set[tuple[str, str, int]] = set()
            for other_source, keys in semantics_by_source.items():
                if other_source != source:
                    others.update(keys)
            unique = own - others
            shared = own & others
            total = len(own)
            kinds = sorted({str(c["source_kind"]) for c in claims if str(c["source"]) == source})
            reports.append(
                {
                    "source": source,
                    "source_kinds": kinds,
                    "semantic_count": total,
                    "unique_semantic_count": len(unique),
                    "shared_semantic_count": len(shared),
                    "structural_novelty_ratio": (len(unique) / total) if total else None,
                    "structural_redundancy_ratio": (len(shared) / total) if total else None,
                    "foreign_lens_quarantined": "foreign_lens" in kinds,
                    "predictive_incremental_information": None,
                    "predictive_status": "UNMEASURED_UNTIL_OUTCOME_VALIDATION",
                }
            )
        return reports

    def snapshot(self, *, as_of: str | None = None) -> dict[str, Any]:
        claims = self._available(as_of)
        grouped: dict[tuple[str, str, int], list[dict[str, Any]]] = {}
        for claim in claims:
            grouped.setdefault(_semantic_group(claim), []).append(claim)

        fused = []
        for key in sorted(grouped):
            semantic_key, regime, horizon_seconds = key
            fused.append(
                {
                    "semantic_key": semantic_key,
                    "regime": regime,
                    "horizon_seconds": horizon_seconds,
                    **self._consensus(grouped[key]),
                }
            )

        return {
            "schema_version": SCHEMA_VERSION,
            "as_of": as_of,
            "claim_count": len(claims),
            "semantic_group_count": len(fused),
            "fused_state": fused,
            "source_contributions": self._source_reports(claims),
            "contracts": {
                "source_identity_preserved": True,
                "disagreement_preserved": True,
                "shared_ancestry_discounted": True,
                "foreign_lenses_quarantined": True,
                "structural_novelty_is_not_predictive_edge": True,
                "protected_validation_required_for_promotion": True,
            },
            "execution_authorized": False,
            "production_decision_authorized": False,
        }
