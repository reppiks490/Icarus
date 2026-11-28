"""First-passage chronology, ambiguity, censoring and causality contracts."""
from datetime import datetime, timedelta, timezone

import pytest

from icarus_engine.omnigenesis.first_passage import label_first_passage


def tape(shocks=None, count=20):
    start=datetime(2026, 1, 1, tzinfo=timezone.utc)
    rows=[]
    shocks=shocks or {}
    for i in range(count):
        t=start+timedelta(minutes=i)
        lo,hi=shocks.get(i,(100,100))
        rows.append({
            "record_id":f"bar_{i:04d}",
            "observed_at":(t-timedelta(seconds=1)).isoformat(),
            "received_at":t.isoformat(),
            "open_ticks":100,
            "high_ticks":hi,"low_ticks":lo,"close_ticks":100,
        })
    return {"asset":"NQ","source_commit":"f"*40,"bars":rows}


def test_first_passage_upper_and_nonoverlap():
    report=label_first_passage(tape({1:(99,105),6:(95,101)},20),
                               upper_distance_ticks=4,lower_distance_ticks=4,
                               horizon_bars=5)
    assert report["label_count"]==3
    assert report["counts"]["UPPER"]==1
    assert report["counts"]["LOWER"]==1
    assert report["counts"]["CENSORED"]==1
    first=report["labels"][0]
    assert first["event"]=="UPPER"
    assert first["first_event_offset_bars"]==1
    assert first["upper_ticks"]==104
    assert first["label_resolved_at"]>first["decision_at"]
    assert report["authority"]["execution_authorized"] is False


def test_ohlc_simultaneous_breach_is_not_optimistically_ordered():
    report=label_first_passage(tape({1:(94,106)}),
                               upper_distance_ticks=4,lower_distance_ticks=4,
                               horizon_bars=3)
    assert report["labels"][0]["event"]=="AMBIGUOUS_BOTH"
    assert report["labels"][0]["label_is_ambiguous"] is True
    assert report["counts"]["AMBIGUOUS_BOTH"]==1


def test_censored_is_not_negative_and_pending_does_not_get_label():
    report=label_first_passage(tape(count=5),
                               upper_distance_ticks=2,lower_distance_ticks=2,
                               horizon_bars=3)
    assert report["labels"][0]["event"]=="CENSORED"
    assert report["labels"][0]["label_is_censored"] is True
    assert report["labels"][0]["first_event_offset_bars"]==4
    assert report["pending_count"]==1


def test_deterministic_report_id_and_empty_event_path():
    x=label_first_passage(tape(),
                          upper_distance_ticks=10,lower_distance_ticks=10,
                          horizon_bars=4)
    y=label_first_passage(tape(),
                          upper_distance_ticks=10,lower_distance_ticks=10,
                          horizon_bars=4)
    assert x==y
    assert x["counts"]["CENSORED"]==4


def test_asof_and_bad_prices_rejected():
    bad=tape()
    bad["bars"][4]["received_at"]="2026-01-01T00:02:00+00:00"
    bad["bars"][4]["observed_at"]="2026-01-01T00:01:00+00:00"
    with pytest.raises(ValueError,match="increase"):
        label_first_passage(bad,upper_distance_ticks=4,lower_distance_ticks=4,horizon_bars=4)
    bad=tape()
    bad["bars"][4]["high_ticks"]=99
    with pytest.raises(ValueError,match="inconsistent"):
        label_first_passage(bad,upper_distance_ticks=4,lower_distance_ticks=4,horizon_bars=4)


def test_episodes_must_not_overlap_and_future_not_ready():
    with pytest.raises(ValueError,match="stride"):
        label_first_passage(tape(),upper_distance_ticks=4,
                            lower_distance_ticks=4,horizon_bars=10,stride=1)


def test_boolean_tick_sizes_and_negatives_fail_closed():
    with pytest.raises(ValueError,match="exact positive"):
        label_first_passage(tape(),upper_distance_ticks=True,
                            lower_distance_ticks=4,horizon_bars=4)
    with pytest.raises(ValueError,match="exact positive"):
        label_first_passage(tape(),upper_distance_ticks=0,
                            lower_distance_ticks=4,horizon_bars=4)
