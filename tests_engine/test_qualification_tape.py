"""CA: entry-lot and replay-evidence tests for the research-only gate."""
import copy

import pytest

from icarus_engine.backtest import _snapshot_hash, _trade_rows
from icarus_engine.emulator import Emulator
from icarus_engine.metrics import Piece
from icarus_engine.pine.timeframe import Bar
from icarus_engine.qualification.tape import assess_port_windows, assess_replay_pair, metrics_from_replay
from icarus_engine.qualification.tape import _date_et


def _result(start=1_700_000_000, pnl=22.0, *, source="a"):
    start = start - start % 1200
    end = start + 86400
    source_config = {"spec": {"symbol": "NQ"}, "base_inputs": {"tp1_pts": 100, "point_value": 1},
                     "pts_scale": 1.0, "mintick": 0.25,
                     "runner_config": {"pts_ref_price": 0, "fixed_pts_scale": 1.0,
                                       "scale_known_at": None},
                     "source": source}
    stamps = [[i, start + i * 1200] for i in range(72)]
    effective_config = {
        "spec": {"symbol": "NQ", "chart_tf": "20", "multiplier": 1.0, "calendar": "crypto",
                 "chart_type": "heikin_ashi", "fill_on": "real", "session": "eth",
                 "commission": 2.0, "slippage_ticks": 2, "capital": 500000.0},
        "base_inputs": {"tp1_pts": 200, "point_value": 1},
        "effective_inputs": {"tp1_pts": 200, "point_value": 1},
        "mintick": 0.25, "window_start": start, "window_end": end,
        "pts_scale": 1.0, "leverage": 50.0,
    }
    return {
        "asset": "NQ", "range": {"start": start, "end": end},
        "config": {
            "fill_on": "real", "chart_type": "heikin_ashi", "window_start": start,
            "window_end": end, "window_boundary_clean": True,
            "window_boundary": {"open_lots": 0, "pending_entries": 0,
                                "pending_closes": 0, "pending_exits": 0},
            "historical_scale_asof_valid": True, "tf": 20, "point_value": 1.0,
            "commission": 2.0, "slippage_ticks": 2, "capital": 500000.0,
            "session": "eth", "pts_scale": 1.0, "leverage": 50.0,
            "overrides": {"tp1_pts": 200},
            "reproducibility": {
                "source_config": source_config, "effective_config": effective_config,
                "source_config_sha256": _snapshot_hash(source_config),
                "effective_config_sha256": _snapshot_hash(effective_config),
                "subbars_sha256": "a" * 64, "deep_sha256": "b" * 64,
                "scale_known_at": None, "historical_scale_asof_valid": True,
                "chart_bar_times": stamps, "chart_bar_times_sha256": _snapshot_hash(stamps),
            },
        },
        "summary": {"net_profit": {"all": pnl}, "total_trades": {"all": 2},
                    "open_trades": {"all": 0}, "open_pnl": {"all": 0}},
        "trades": [
            {"no": 1, "lot_id": 101, "type": "long", "entry_ts": start + 3600,
             "exit_ts": start + 4800, "entry_px": 100.0, "exit_px": 110.0,
             "entry_signal": "L", "exit_signal": "L_TP1", "qty": 1, "entry_qty": 2,
             "commission": 4.0, "pnl": 6.0, "bars": 1, "entry_bar": 3,
             "exit_bar": 4, "open": False},
            {"no": 2, "lot_id": 101, "type": "long", "entry_ts": start + 3600,
             "exit_ts": start + 6000, "entry_px": 100.0, "exit_px": 120.0,
             "entry_signal": "L", "exit_signal": "L_TP2", "qty": 1, "entry_qty": 2,
             "commission": 4.0, "pnl": 16.0, "bars": 2, "entry_bar": 3,
             "exit_bar": 5, "open": False},
        ],
    }


def test_partial_exits_count_as_one_position_and_runner():
    report = metrics_from_replay(_result())
    assert report["trades"] == 1
    assert report["win_rate"] == 100
    assert report["expectancy"] == 22
    assert report["runner_legs"] == 1
    assert report["runner_win_rate"] == 100
    assert report["tp1_rate"] == report["tp2_rate"] == 100
    assert report["mean_hold"] == 2


def test_same_bar_same_price_separate_lots_stay_separate():
    result = _result(pnl=28)
    second = copy.deepcopy(result["trades"][0])
    second.update(no=3, lot_id=102, entry_qty=1)
    result["trades"].append(second)
    result["summary"]["total_trades"]["all"] = 3
    report = metrics_from_replay(result)
    assert report["trades"] == 2
    assert report["runner_legs"] == 1
    assert report["win_rate"] == 100


@pytest.mark.parametrize("mutate", [
    lambda r: r["trades"][0].update(pnl=100),
    lambda r: r["trades"][0].update(commission=0),
    lambda r: r["trades"][0].update(lot_id=0),
    lambda r: r["trades"][0].update(entry_qty=3),
    lambda r: r["trades"].pop(),
    lambda r: r["trades"][0].update(open=True),
    lambda r: r["trades"][0].update(exit_ts=r["config"]["window_end"] + 1),
    lambda r: r["trades"][0].update(exit_ts=r["trades"][0]["entry_ts"]),
    lambda r: r["summary"]["open_trades"].update(all=1),
    lambda r: r["config"]["window_boundary"].update(open_lots=1),
    lambda r: r["config"]["window_boundary"].update(pending_exits=1),
    lambda r: r["config"]["reproducibility"].update(scale_known_at=r["config"]["window_end"]),
    lambda r: r["trades"][0].update(exit_ts=r["trades"][0]["entry_ts"] + 1),
    lambda r: r["config"].update(slippage_ticks=-1),
    lambda r: r["config"].update(window_boundary_clean=False),
    lambda r: r["config"].update(historical_scale_asof_valid=False),
    lambda r: r["config"]["reproducibility"].update(source_config_sha256="c" * 64),
])
def test_tampered_or_censored_tape_fails_closed(mutate):
    result = _result()
    mutate(result)
    with pytest.raises(ValueError):
        metrics_from_replay(result)


def test_pair_rejects_overlap_and_different_source():
    tune = _result()
    hold = _result(start=tune["config"]["window_end"] + 86400)
    good = assess_replay_pair(tune, hold)
    assert good["status"] == "thresholds_failed"
    assert good["replay_structure_checked"] is True
    assert good["engine_replay_checked"] is False
    assert good["candidate_qualified"] is False
    overlap = _result(start=tune["config"]["window_end"] - 1)
    assert assess_replay_pair(tune, overlap)["status"] == "insufficient_evidence"
    different = _result(start=hold["config"]["window_start"], source="different")
    assert assess_replay_pair(tune, different)["status"] == "insufficient_evidence"


def test_pair_rejects_claimed_snapshot_tampering_and_malformed_results():
    tune = _result()
    hold = _result(start=tune["config"]["window_end"] + 86400)
    hold["config"]["reproducibility"]["effective_config"]["spec"]["multiplier"] = 20.0
    effective = hold["config"]["reproducibility"]["effective_config"]
    hold["config"]["reproducibility"]["effective_config_sha256"] = _snapshot_hash(effective)
    assert assess_replay_pair(tune, hold)["status"] == "insufficient_evidence"
    hold = _result(start=tune["config"]["window_end"] + 86400)
    hold["summary"] = None
    assert assess_replay_pair(tune, hold)["status"] == "insufficient_evidence"
    hold = _result(start=tune["config"]["window_end"] + 86400)
    hold["auxiliary"] = float("nan")
    assert assess_replay_pair(tune, hold)["status"] == "insufficient_evidence"


def test_replay_rejects_compressed_or_missing_chart_bars_even_with_updated_digest():
    result = _result()
    rep = result["config"]["reproducibility"]
    for index in range(1, len(rep["chart_bar_times"])):
        rep["chart_bar_times"][index][1] = rep["chart_bar_times"][0][1] + index * 8
    rep["chart_bar_times_sha256"] = _snapshot_hash(rep["chart_bar_times"])
    with pytest.raises(ValueError, match="calendar bucket"):
        metrics_from_replay(result)

    result = _result()
    rep = result["config"]["reproducibility"]
    rep["chart_bar_times"].pop(-1)
    rep["chart_bar_times_sha256"] = _snapshot_hash(rep["chart_bar_times"])
    with pytest.raises(ValueError, match="range differs"):
        metrics_from_replay(result)

    result = _result()
    rep = result["config"]["reproducibility"]
    rep["chart_bar_times"] = [item for item in rep["chart_bar_times"] if item[0] != 20]
    for index, item in enumerate(rep["chart_bar_times"]):
        item[0] = index
    rep["chart_bar_times_sha256"] = _snapshot_hash(rep["chart_bar_times"])
    with pytest.raises(ValueError, match="unexplained gap"):
        metrics_from_replay(result)


def test_in_process_replay_is_distinguished_from_claimed_json(monkeypatch):
    import icarus_engine.backtest as backtest

    tune = _result()
    hold = _result(start=tune["config"]["window_end"] + 86400)
    calls = []

    def replay(port, asset, **kwargs):
        calls.append((port, asset, kwargs))
        return tune if len(calls) == 1 else hold

    monkeypatch.setattr(backtest, "run_backtest", replay)
    monkeypatch.setattr(backtest, "freeze_replay_port", lambda port, asset: port)
    port = object()
    report = assess_port_windows(port, "NQ", patch={"tp1_pts": 200},
                                 tune_start=tune["config"]["window_start"],
                                 tune_end=tune["config"]["window_end"],
                                 hold_start=hold["config"]["window_start"],
                                 hold_end=hold["config"]["window_end"])
    assert len(calls) == 2
    assert all(c[2]["fill_on"] == "real" and c[2]["chart_type"] == "heikin_ashi" for c in calls)
    assert report["engine_replay_checked"] is True
    assert report["candidate_qualified"] is False


def test_overnight_uses_historical_iana_dst_not_pinned_three_year_table():
    from datetime import datetime, timezone

    before = int(datetime(2023, 7, 1, 4, 30, tzinfo=timezone.utc).timestamp())
    after = int(datetime(2023, 7, 1, 5, 30, tzinfo=timezone.utc).timestamp())
    assert _date_et(before) == _date_et(after)


def test_emulator_lot_identity_survives_multiple_exit_pieces():
    em = Emulator(commission=0, mintick=1, contract_size=1)
    em.entry("L", 1, 2)
    em.process_bar(Bar(60, 100, 100, 100, 100, 1), 0)
    em.exit("TP1", "L", qty=1, limit=101, comment_profit="L_TP1")
    em.process_bar(Bar(120, 100, 101, 100, 101, 1), 1)
    em.close("L", "L_EOD")
    em.process_bar(Bar(180, 102, 102, 102, 102, 1), 2)
    assert len(em.closed) == 2
    assert em.closed[0].lot_id == em.closed[1].lot_id > 0
    pieces = [Piece(no=i, direction=trade.direction, qty=trade.qty,
                    entry_ts=trade.entry_ts, entry_px=trade.entry_price,
                    exit_ts=trade.exit_ts, exit_px=trade.exit_price,
                    exit_signal=trade.exit_comment, pnl=trade.profit,
                    commission=0, lot_id=trade.lot_id, entry_qty=trade.entry_qty)
              for i, trade in enumerate(em.closed, 1)]
    rows = _trade_rows(pieces, [], point_value=1)
    assert [row["lot_id"] for row in rows] == [em.closed[0].lot_id] * 2
    assert [row["entry_qty"] for row in rows] == [2, 2]
