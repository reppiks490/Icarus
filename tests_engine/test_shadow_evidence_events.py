import pytest

from icarus_engine.intelligence_fabric import IntelligenceFabric
from icarus_engine.shadow_evidence_events import publish_shadow_evidence, shadow_evidence_event


def evidence(**changes):
    row = {
        "schema": "icarus.real_price_shadow/1",
        "enabled": True,
        "status": "READY",
        "execution_authorized": False,
        "fill_basis": "STANDARD_REAL_BAR_EMULATOR",
        "signal_basis": "PRIMARY_ICARUS_ORDER_INTENTS",
        "asset": "NQ=F",
        "provenance": {"price_provider": "databento", "timeframe_minutes": 1},
        "primary_entry_fills": 4,
        "shadow_entry_fills": 3,
        "entry_fill_parity": 0.75,
        "outcome_matrix": {"win": {"win": 2}},
        "excluded_admin_flatten_lot_trade_pieces": {"primary": 0, "shadow": 0},
        "administrative_censored_shadow_positions": 2,
        "primary": {"net": 120.0, "warmup_net": 0.0, "live_net": 120.0},
        "real_price_shadow": {"net": 50.0, "warmup_net": 0.0, "live_net": 50.0},
        "net_realization_ratio": 50.0 / 120.0,
        "paired_profit_capture": None,
        "recent_intents": [{"alert_message": "must not be published"}],
        "recent_entry_fill_pairs": [{"price": 12345.0}],
    }
    row.update(changes)
    return row


def test_explicit_shadow_event_is_compact_content_addressed_and_non_authoritative():
    event = shadow_evidence_event(
        evidence(), run_id="run-01", observed_at="2026-10-15T16:00:00Z",
        received_at="2026-10-15T16:01:00Z")
    row = event.normalized()
    assert row["event_type"] == "research"
    assert row["source_kind"] == "experiment"
    assert row["assets"] == ["NQ=F"]
    assert row["execution_authorized"] is False
    assert row["production_decision_authorized"] is False
    assert row["payload"]["execution_authorized"] is False
    assert row["payload"]["evidence"]["provenance"]["price_provider"] == "databento"
    assert row["payload"]["evidence"]["excluded_admin_flatten_lot_trade_pieces"] == {
        "primary": 0, "shadow": 0,
    }
    assert row["payload"]["evidence"]["administrative_censored_shadow_positions"] == 2
    assert "recent_intents" not in row["payload"]["evidence"]
    assert "recent_entry_fill_pairs" not in row["payload"]["evidence"]
    assert row["evidence_ids"][0].startswith("sha256:")


def test_event_evidence_is_snapshotted_before_the_content_digest_is_assigned():
    source = evidence()
    event = shadow_evidence_event(
        source, run_id="run-01", observed_at="2026-10-15T16:00:00Z",
        received_at="2026-10-15T16:01:00Z")
    source["provenance"]["price_provider"] = "mutated-after-event-creation"
    assert event.normalized()["payload"]["evidence"]["provenance"]["price_provider"] == "databento"


def test_explicit_publish_is_idempotent_and_queryable_by_asset():
    with IntelligenceFabric(":memory:") as fabric:
        kwargs = {"run_id": "run-01", "observed_at": "2026-10-15T16:00:00Z",
                  "received_at": "2026-10-15T16:01:00Z"}
        first = publish_shadow_evidence(fabric, evidence(), **kwargs)
        second = publish_shadow_evidence(fabric, evidence(), **kwargs)
        assert first["event_id"] == second["event_id"]
        assert first["idempotent"] is False
        assert second["idempotent"] is True
        assert first["execution_authorized"] is False
        rows = fabric.query(channel="real_price_shadow", assets=["NQ=F"])
        assert len(rows) == 1
        assert rows[0]["payload"]["evidence"]["primary_entry_fills"] == 4


@pytest.mark.parametrize("changes, message", [
    ({"schema": "other"}, "unsupported shadow summary schema"),
    ({"enabled": False}, "enabled twin"),
    ({"execution_authorized": True}, "must explicitly deny execution authority"),
    ({"status": "DISABLED"}, "unsupported status"),
    ({"provenance": None}, "provenance mapping"),
])
def test_shadow_event_rejects_invalid_or_authority_expanding_evidence(changes, message):
    with pytest.raises(ValueError, match=message):
        shadow_evidence_event(evidence(**changes), run_id="run-01",
                              observed_at="2026-10-15T16:00:00Z",
                              received_at="2026-10-15T16:01:00Z")
