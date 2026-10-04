# CL (Claude, Anthropic) — 2026-10-04 — tests for icarus_futures: contracts, order state machine, journal, recovery, chaos
from datetime import date, datetime, timezone

import pytest

from icarus_futures import contracts
from icarus_futures.engine import ExecutionEngine
from icarus_futures.journal import Journal, JournalCorrupt
from icarus_futures.orders import Intent, OrderBook, S
from icarus_futures.risk import PortfolioState, RiskConfig, RiskGovernor
from icarus_futures.venue import SimVenue

NOW = datetime(2026, 10, 5, 14, 0, tzinfo=timezone.utc)
SYM = "MNQZ26"


def _engine(tmp_path, faults=None, mode="SIM", cfg=None):
    v = SimVenue(faults=dict(faults or {}))
    v.mark(SYM, 20000.0)
    e = ExecutionEngine(v, RiskGovernor(cfg or RiskConfig()), Journal(str(tmp_path / "j.jsonl")), mode=mode)
    e.state.marks[SYM] = 20000.0
    e.state.data_age_s[SYM] = 1.0
    return e, v


def _buy(qty=2, kind="MARKET", price=None, ts="2026-10-05T14:00:00Z", **kw):
    return Intent("t", SYM, "BUY", qty, kind, price, signal_ts=ts, **kw)


# ---------------- contracts ----------------
def test_continuous_identity_resolves_and_rolls():
    assert contracts.resolve("NQ1!", date(2026, 9, 9))["contract"] == "NQU26"
    assert contracts.resolve("NQ1!", date(2026, 9, 10))["contract"] == "NQZ26"   # roll = 3rd Fri (18th) - 8 days
    assert contracts.resolve("CME_MINI:MNQ1!", date(2026, 12, 31))["contract"] == "MNQH27"
    assert contracts.resolve("NQ2!", date(2026, 9, 9))["contract"] == "NQZ26"
    g = contracts.resolve("GC1!", date(2026, 9, 1))
    assert g["contract"] == "GCV26" and g["roll_date"] < "2026-09-30"
    with pytest.raises(ValueError):
        contracts.parse_continuous("NQZ2026")   # expiring codes are never user-facing


def test_contract_economics():
    s = contracts.SPECS
    assert s["MNQ"].point_value == 2.0 and s["NQ"].point_value == 20.0 and s["ES"].point_value == 50.0
    assert s["MNQ"].full_equivalent(10) == pytest.approx(1.0)
    assert s["MGC"].notional(1, 2500.0) == pytest.approx(25_000.0)


# ---------------- state machine ----------------
def test_intent_id_is_deterministic_and_duplicates_are_suppressed(tmp_path):
    e, v = _engine(tmp_path)
    a = e.submit(_buy(), NOW)
    b = e.submit(_buy(), NOW)
    assert a["order_id"] == b["order_id"] and b["status"] == "DUPLICATE_SUPPRESSED"
    assert len([o for o in v._orders.values()]) == 1


def test_market_order_fills_and_tracks_average_price(tmp_path):
    e, v = _engine(tmp_path, faults={"partial_fill": 1})
    r = e.submit(_buy(qty=4), NOW)
    v.mark(SYM, 20001.0)
    e.pump()
    v.mark(SYM, 20003.0)
    e.pump()
    o = e.book.orders[r["order_id"]]
    assert o.state == S.FILLED and o.filled == 4 and e.book.positions[SYM] == 4
    assert o.avg_price == pytest.approx((2 * 20001.25 + 2 * 20003.25) / 4)


def test_duplicate_fill_reports_are_ignored(tmp_path):
    e, v = _engine(tmp_path, faults={"duplicate_fill": 1})
    r = e.submit(_buy(qty=2), NOW)
    v.mark(SYM, 20000.0)
    e.pump()
    assert e.book.positions[SYM] == 2 and e.book.orders[r["order_id"]].state == S.FILLED


def test_fill_during_cancel_wins_and_late_cancel_ack_is_ignored():
    b = OrderBook()
    o, _ = b.add(_buy(qty=2, kind="LIMIT", price=19990.0))
    b.on_sent(o.id); b.on_ack(o.id, "S1")
    assert b.on_cancel_requested(o.id)
    b.on_fill(o.id, "F1", 2, 19990.0)
    b.on_cancel_ack(o.id)
    assert o.state == S.FILLED and b.positions[SYM] == 2


def test_overfill_is_ambiguous_and_alarms():
    b = OrderBook()
    o, _ = b.add(_buy(qty=1))
    b.on_sent(o.id); b.on_ack(o.id, "S1")
    b.on_fill(o.id, "F1", 3, 20000.0)
    assert o.state == S.AMBIGUOUS and b.alarms


def test_reject_is_classified(tmp_path):
    e, _ = _engine(tmp_path, faults={"reject:INSUFFICIENT_MARGIN": 1})
    r = e.submit(_buy(), NOW)
    o = e.book.orders[r["order_id"]]
    assert o.state == S.REJECTED and o.reject == dict(code="INSUFFICIENT_MARGIN", retryable=False, raw="INSUFFICIENT_MARGIN")


def test_oco_sibling_cancelled_when_one_leg_fills():
    b = OrderBook()
    tp, _ = b.add(Intent("t", SYM, "SELL", 1, "LIMIT", 20100.0, "x", oco_group="g1"))
    sl, _ = b.add(Intent("t", SYM, "SELL", 1, "STOP", 19900.0, "x", oco_group="g1"))
    for o, bid in ((tp, "S1"), (sl, "S2")):
        b.on_sent(o.id); b.on_ack(o.id, bid)
    b.on_fill(tp.id, "F1", 1, 20100.0)
    assert tp.state == S.FILLED and sl.state == S.PENDING_CANCEL


# ---------------- ambiguity, reconciliation, recovery ----------------
def test_lost_ack_is_ambiguous_blocks_risk_then_reconciles(tmp_path):
    e, v = _engine(tmp_path, faults={"drop_ack": 1})
    r = e.submit(_buy(kind="LIMIT", price=19000.0), NOW)
    assert r["status"] == "AMBIGUOUS"
    blocked = e.submit(_buy(ts="2026-10-05T14:01:00Z"), NOW)
    assert blocked["status"] == "VETOED" and "AMBIGUOUS_ORDERS" in blocked["codes"]
    rep = e.reconcile()
    assert r["order_id"] in rep["resolved"] and e.book.orders[r["order_id"]].state == S.WORKING
    assert e.submit(_buy(ts="2026-10-05T14:02:00Z"), NOW)["status"] in ("FILLED", "WORKING")


def test_disconnect_mid_submit_is_ambiguous_not_retried(tmp_path):
    e, v = _engine(tmp_path, faults={"disconnect": 1})
    r = e.submit(_buy(), NOW)
    assert r["status"] == "AMBIGUOUS" and len(v._orders) == 0
    v.connected = True
    rep = e.reconcile()
    assert rep["not_at_venue"] == [r["order_id"]]


def test_restart_rebuilds_from_journal_without_replaying_orders(tmp_path):
    e, v = _engine(tmp_path)
    r = e.submit(_buy(qty=3), NOW)
    v.mark(SYM, 20002.0)
    e.pump()
    w = e.submit(_buy(qty=1, kind="LIMIT", price=19000.0, ts="2026-10-05T14:05:00Z"), NOW)
    sent_before = len(v._orders)
    e2 = ExecutionEngine(v, RiskGovernor(), Journal(str(tmp_path / "j.jsonl")), mode="SIM")
    assert len(v._orders) == sent_before                       # nothing resubmitted
    assert e2.book.positions[SYM] == 3 and e2.book.orders[r["order_id"]].state == S.FILLED
    assert e2.book.orders[w["order_id"]].state == S.WORKING and e2.needs_reconcile
    assert e2.submit(_buy(qty=3), NOW)["status"] == "DUPLICATE_SUPPRESSED"     # same intent: never re-sent
    assert "AMBIGUOUS_ORDERS" in e2.submit(_buy(qty=1), NOW)["codes"]           # new risk waits for reconcile
    e2.reconcile()
    assert not e2.needs_reconcile and not e2.state.broker_mismatch


def test_position_mismatch_blocks_new_risk_but_allows_reduction(tmp_path):
    e, v = _engine(tmp_path)
    e.submit(_buy(qty=2), NOW)
    v.mark(SYM, 20000.0)
    e.pump()
    v._pos[SYM] = 5                          # venue truth diverges (e.g. a manual trade)
    assert e.reconcile()["position_mismatch"][SYM] == dict(engine=2, venue=5)
    assert "BROKER_MISMATCH" in e.submit(_buy(qty=1, ts="t2"), NOW)["codes"]
    out = e.flatten_all(NOW)
    assert out and out[0]["status"] in ("FILLED", "WORKING", "SUBMITTED")


def test_journal_torn_tail_tolerated_but_mid_file_corruption_fails_closed(tmp_path):
    p = tmp_path / "j.jsonl"
    j = Journal(str(p))
    j.append("a", {"x": 1}); j.append("b", {"x": 2})
    with open(p, "a") as f:
        f.write('{"kind":"c","pay')                 # process died mid-write
    j2 = Journal(str(p))
    assert j2.torn_tail and len(j2.replay()) == 2
    lines = p.read_text().split("\n")
    lines[0] = lines[0].replace('"x":1', '"x":9')
    p.write_text("\n".join(lines))
    with pytest.raises(JournalCorrupt):
        Journal(str(p))


# ---------------- mode identity ----------------
def test_live_mode_fails_closed_without_governance(tmp_path):
    v = SimVenue()
    with pytest.raises(PermissionError):
        ExecutionEngine(v, RiskGovernor(), Journal(str(tmp_path / "j.jsonl")), mode="LIVE",
                        governance_path=str(tmp_path / "missing.json"))


def test_shadow_records_without_venue_and_snapshot_states(tmp_path):
    e = ExecutionEngine(None, RiskGovernor(), Journal(str(tmp_path / "j.jsonl")), mode="SHADOW")
    e.state.marks[SYM] = 20000.0
    e.state.data_age_s[SYM] = 1.0
    assert e.submit(_buy(), NOW)["status"] == "SHADOW_RECORDED"
    snap = e.snapshot()
    assert snap["ui_state"] == "SHADOW" and snap["execution_authorized"] is False and snap["health"] == "GREEN"
