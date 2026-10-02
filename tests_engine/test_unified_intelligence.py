from __future__ import annotations

from icarus_engine.brain import SUBSYSTEMS
from icarus_engine.unified_intelligence import IntelligenceClaim, UnifiedIntelligenceSpine


def _claim(source: str, stance: float, **overrides):
    body = dict(
        source=source,
        source_kind="native",
        semantic_key="NQ:time_price_phase",
        stance=stance,
        confidence=0.8,
        evidence_class="derived",
        observed_at="2026-10-01T14:00:00Z",
        received_at="2026-10-01T14:00:01Z",
        regime="RTH",
        horizon_seconds=300,
        lineage=(source + ":root",),
        falsifiers=("future outcome disagrees",),
        details={"test": True},
    )
    body.update(overrides)
    return IntelligenceClaim(**body)


def test_unified_spine_preserves_disagreement_and_never_grants_authority():
    spine = UnifiedIntelligenceSpine()
    spine.ingest(_claim("chronofold", 0.9))
    spine.ingest(_claim("f4d3-lens", -0.7, source_kind="foreign_lens"))
    out = spine.snapshot()

    assert out["claim_count"] == 2
    assert out["fused_state"][0]["directional_conflict"] is True
    assert out["fused_state"][0]["effective_independent_families"] == 2
    assert out["execution_authorized"] is False
    assert out["production_decision_authorized"] is False

    foreign = next(row for row in out["source_contributions"] if row["source"] == "f4d3-lens")
    assert foreign["foreign_lens_quarantined"] is True
    assert foreign["predictive_incremental_information"] is None


def test_unified_spine_discounts_shared_ancestry_instead_of_double_counting():
    spine = UnifiedIntelligenceSpine()
    shared = ("same-market-record", "same-derived-feature")
    spine.ingest(_claim("psi", 0.6, lineage=shared, confidence=0.7))
    spine.ingest(_claim("apex", 0.7, lineage=shared, confidence=0.9))
    out = spine.snapshot()
    fused = out["fused_state"][0]

    assert fused["raw_claim_count"] == 2
    assert fused["effective_independent_families"] == 1
    assert fused["shared_ancestry_discounted"] == 1
    assert fused["consensus_stance"] == 0.7


def test_unified_spine_is_idempotent_and_causally_as_of():
    spine = UnifiedIntelligenceSpine()
    first = spine.ingest(_claim("chronofold", 0.4))
    second = spine.ingest(_claim("chronofold", 0.4))
    assert first["idempotent"] is False
    assert second["idempotent"] is True

    before_receipt = spine.snapshot(as_of="2026-10-01T14:00:00Z")
    after_receipt = spine.snapshot(as_of="2026-10-01T14:00:01Z")
    assert before_receipt["claim_count"] == 0
    assert after_receipt["claim_count"] == 1


def test_unified_spine_reports_structural_novelty_without_calling_it_edge():
    spine = UnifiedIntelligenceSpine()
    spine.ingest(_claim("chronofold", 0.4, semantic_key="shared"))
    spine.ingest(_claim("psi", 0.5, semantic_key="shared"))
    spine.ingest(_claim("f4d3-lens", 0.8, source_kind="foreign_lens", semantic_key="foreign-only"))

    out = spine.snapshot()
    f4d3 = next(row for row in out["source_contributions"] if row["source"] == "f4d3-lens")
    chronofold = next(row for row in out["source_contributions"] if row["source"] == "chronofold")

    assert f4d3["structural_novelty_ratio"] == 1.0
    assert f4d3["structural_redundancy_ratio"] == 0.0
    assert chronofold["structural_novelty_ratio"] == 0.0
    assert chronofold["structural_redundancy_ratio"] == 1.0
    assert f4d3["predictive_status"] == "UNMEASURED_UNTIL_OUTCOME_VALIDATION"


def test_unavailable_claim_cannot_carry_confidence():
    try:
        _claim("broken", 0.0, evidence_class="unavailable", confidence=0.5).normalized()
    except ValueError as ex:
        assert "zero confidence" in str(ex)
    else:
        raise AssertionError("unavailable evidence with confidence must fail closed")


def test_unified_intelligence_spine_is_registered_in_adaptive_brain():
    rows = {row["id"]: row for row in SUBSYSTEMS}
    assert "unified-intelligence" in rows
    assert rows["unified-intelligence"]["owner"] == "omega"
    assert "redundancy" in rows["unified-intelligence"]["job"].lower()
    assert "disagreement" in rows["unified-intelligence"]["job"].lower()
