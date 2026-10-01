from __future__ import annotations


def _participant_state():
    return {
        "schema_version": "icarus-apex-participant-state-v1",
        "asset": "NQ",
        "as_of": "2026-10-01T14:00:00Z",
        "horizon_seconds": 300,
        "status": "ACTIVE",
        "classes": [{
            "participant_class": "discretionary_retail",
            "reported_class": "discretionary_retail",
            "nominal_evidence_count": 1,
            "effective_independent_families": 1,
            "evidence_integrity_ok": True,
            "confidence": 0.6,
            "long_support": 1,
            "short_support": 0,
            "components": [{
                "metric": "entry_density", "direction": "long",
                "price_low": 24990.0, "price_high": 25010.0,
                "value": 0.7, "confidence": 0.6, "evidence_id": "e1",
                "kind": "reconstructed",
            }],
        }],
        "execution_authorized": False,
        "production_decision_authorized": False,
    }


def _force_field():
    return {
        "schema_version": "icarus-apex-pressure-tensor-v1",
        "as_of": "2026-10-01T14:00:00Z",
        "asset": "NQ",
        "cells": [{
            "price": 25000.0, "horizon_seconds": 300, "status": "ACTIVE",
            "contributions": [{
                "source": "participant", "participant_class": "discretionary_retail",
                "direction": "sell", "pressure": 0.5, "signed_pressure": -0.5,
                "confidence": 0.6, "evidence_id": "e1",
            }],
            "net_pressure": -0.5, "confidence": 0.6,
        }],
        "liquidity_context": {}, "crowd_context": {},
        "execution_authorized": False,
        "production_decision_authorized": False,
    }


def test_participant_state_is_append_only_idempotent_and_reopens(tmp_path):
    from icarus_engine.apex.store import ApexStore
    store=ApexStore(tmp_path)
    one=store.record_participant_state(_participant_state())
    two=store.record_participant_state(_participant_state())
    assert one["idempotent"] is False and two["idempotent"] is True
    assert one["state_id"] == two["state_id"]
    store.close()
    reopened=ApexStore(tmp_path)
    rows=reopened.participant_states_as_of("2026-10-01T14:00:00Z",asset="NQ")
    assert len(rows)==1 and rows[0]["state_id"]==one["state_id"]


def test_participant_state_historical_as_of_and_lineage_retention(tmp_path):
    from icarus_engine.apex.store import ApexStore
    store=ApexStore(tmp_path)
    state=_participant_state(); state["source_evidence_ids"]=["e1","e2"]
    store.record_participant_state(state)
    assert store.participant_states_as_of("2026-10-01T13:59:59Z")==[]
    row=store.participant_states_as_of("2026-10-01T14:00:00Z")[0]
    assert row["source_evidence_ids"]==["e1","e2"]


def test_force_field_retry_is_idempotent_and_historical(tmp_path):
    from icarus_engine.apex.store import ApexStore
    store=ApexStore(tmp_path)
    field=_force_field(); field["source_evidence_ids"]=["e1"]
    a=store.record_force_field(field); b=store.record_force_field(field)
    assert a["field_id"]==b["field_id"] and b["idempotent"] is True
    assert store.force_fields_as_of("2026-10-01T13:59:59Z")==[]
    rows=store.force_fields_as_of("2026-10-01T14:00:00Z",asset="NQ")
    assert rows[0]["source_evidence_ids"]==["e1"]
