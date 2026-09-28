# Claude (Opus 5.5) — 2026-09-27. Regressions for the final code review of PRs #30-#36: minute-floored candidate
# stamps (lookahead), the ledger the validators trust, the forming last bar, significance, and fail-closed edges.
import json
import random
import threading
from http.client import HTTPConnection

import pytest

from icarus_engine.audit.run import score_pair
from icarus_engine.events.calendar import seed_events

T0 = 1_700_000_040            # a whole minute


def _bars(closes, stamps=None, step=60):
    out = []
    for i, c in enumerate(closes):
        o = closes[i - 1] if i else c
        out.append({"ts": stamps[i] if stamps else T0 + i * step, "open": o, "high": max(o, c) + 0.1,
                    "low": min(o, c) - 0.1, "close": c, "tide_long": 0.0, "tide_short": 0.0})
    return out


# ---- B1: minute-floored candidate stamps -------------------------------------------------------------

def _floored_market(n=400, seed=8):
    """TradingView range exports stamp bars at the minute floor plus a millisecond counter. Here minute i holds
    range bars A (stamped i.000) and B (stamped i.001); B keeps forming until the next minute's A opens, so B's
    move overlaps the NEXT execution minute. A stamp-trusting rule reads B as closed before that minute."""
    rng = random.Random(seed)
    m = [rng.choice((1.0, -1.0)) for _ in range(n + 2)]
    ex = [100.0]
    for i in range(1, n):
        ex.append(ex[-1] + m[i])                     # execution minute i moves by m[i]
    closes, stamps, px = [], [], 100.0
    for i in range(n):
        px += m[i]; closes.append(px); stamps.append(T0 + 60 * i)             # A: minute i's own move
        px += m[i + 1]; closes.append(px); stamps.append(T0 + 60 * i + 0.001)  # B: overlaps minute i+1
    return _bars(ex), _bars(closes, stamps)


def test_a_minute_floored_candidate_cannot_fake_a_lead():
    ex, cand = _floored_market()
    r = score_pair(ex, cand, seed_events(), "AAPL", "NQ")
    assert r["overlap"] > 200
    assert 0.35 < r["sign_agree"] < 0.65          # the stamp-trusting rule scored 1.0 here


def test_the_family_can_be_declared_for_a_floored_candidate():
    from icarus_engine.audit.lead import completed_before
    cand = [{"ts": T0}, {"ts": T0 + 60}, {"ts": T0 + 120}]       # whole minutes, but range bars
    assert completed_before(cand, T0 + 60) == 0                  # clock bars: bar 0 closed when bar 1 opened
    assert completed_before(cand, T0 + 60, floored=True) is None  # range bars: bar 1 opened somewhere in minute 1
    assert completed_before(cand, T0 + 120, floored=True) == 0


def test_exact_clock_candidates_keep_their_one_bar_lead():
    rng = random.Random(3)
    moves = [rng.choice((1.0, -1.0)) for _ in range(300)]
    cand, ex = [100.0], [100.0, 100.0]
    for mv in moves[1:]:
        cand.append(cand[-1] + mv)
        ex.append(ex[-1] + mv)
    r = score_pair(_bars(ex), _bars(cand), seed_events(), "AAPL", "NQ", cand_floored=False)   # declared 1m candles
    assert r["sign_agree"] == 1.0


# ---- B2: the ledger comes from configuration, not from the artifact ----------------------------------------

def _pattern_csv(path, n=900):
    rows, px = [], 100.0
    for i in range(n):
        step = 1 if (i // 8) % 2 == 0 else -1
        rows.append(f"{T0 + i * 60},{px},{max(px, px + step)},{min(px, px + step)},{px + step}")
        px += step
    path.write_text("time,open,high,low,close\n" + "\n".join(rows) + "\n")
    return path


def test_default_ledger_is_one_absolute_place(tmp_path, monkeypatch):
    from icarus_engine.trainers import ledger
    monkeypatch.setenv("ICARUS_LEDGER", str(tmp_path / "canon.sqlite3"))
    assert ledger.canonical() == (tmp_path / "canon.sqlite3").resolve()
    monkeypatch.delenv("ICARUS_LEDGER")
    assert ledger.canonical().is_absolute() and ledger.canonical().name == "holdout_ledger.sqlite3"


def test_an_artifact_claimed_in_another_ledger_does_not_qualify(tmp_path, monkeypatch):
    from icarus_engine.trainers.dataset import attach_labels, load_ohlc
    from icarus_engine.trainers.qualify import qualify_xgb
    from icarus_engine.trainers.run import train_xgb_file
    canon = tmp_path / "canon.sqlite3"
    monkeypatch.setenv("ICARUS_LEDGER", str(canon))
    csv = _pattern_csv(tmp_path / "NQ.csv")
    labeled = attach_labels(load_ohlc(csv), "clock_minutes")
    side = train_xgb_file(csv, "minutes", "ohlc", "NQ", out=tmp_path / "a" / "x.json", ledger=tmp_path / "side.sqlite3")
    assert side["status"] == "fitted" and side["holdout_claim"]["status"] == "NEW"
    assert qualify_xgb(tmp_path / "a" / "x.json", "NQ", "clock_minutes", labeled=labeled)[0] == "BLOCKED_HOLDOUT_REUSE"
    home = train_xgb_file(csv, "minutes", "ohlc", "NQ", out=tmp_path / "b" / "x.json")      # canonical ledger
    assert home["holdout_claim"]["status"] == "NEW"
    assert qualify_xgb(tmp_path / "b" / "x.json", "NQ", "clock_minutes", labeled=labeled)[0] == "VALID_RAW_CHALLENGER"


def test_an_unreadable_ledger_is_unknown_not_reuse(tmp_path):
    from icarus_engine.trainers.dataset import attach_labels, load_ohlc
    from icarus_engine.trainers.qualify import qualify_xgb
    from icarus_engine.trainers.run import train_xgb_file
    csv = _pattern_csv(tmp_path / "NQ.csv")
    led = tmp_path / "l.sqlite3"
    train_xgb_file(csv, "minutes", "ohlc", "NQ", out=tmp_path / "x.json", ledger=led)
    led.unlink()
    labeled = attach_labels(load_ohlc(csv), "clock_minutes")
    assert qualify_xgb(tmp_path / "x.json", "NQ", "clock_minutes", labeled=labeled, ledger_path=led)[0] == "UNKNOWN"


# ---- B3: the export's last bar may still be forming --------------------------------------------------------

def test_the_last_row_of_an_export_is_never_used(tmp_path):
    from icarus_engine.trainers.integrity import inspect_ohlc
    p = tmp_path / "d.csv"
    rows = [f"{T0 + i * 86400},100,101,99,100.5,1000000" for i in range(30)] + [f"{T0 + 30 * 86400},100,100.2,99.9,100.1,55866"]
    p.write_text("time,open,high,low,close,Volume\n" + "\n".join(rows) + "\n")
    bars, m = inspect_ohlc(p)
    assert len(bars) == 30 and bars[-1]["ts"] == T0 + 29 * 86400
    assert m["trailing_dropped"] == 1 and m["rows_used"] == 30


# ---- B4: VALID needs significance that survives serial correlation --------------------------------------

def test_newey_west_widens_the_error_of_a_correlated_series():
    from icarus_engine.trainers.metrics import paired_test
    rng = random.Random(1)
    white = [rng.gauss(-0.02, 1.0) for _ in range(400)]
    sticky, x = [], 0.0
    for e in white:
        x = 0.9 * x + e
        sticky.append(x * 0.3 - 0.02)
    assert paired_test(sticky)["se"] > paired_test(sticky, lag=0)["se"] * 1.5
    assert 0.0 <= paired_test(white)["p"] <= 1.0


def test_valid_requires_significance_against_both_baselines(tmp_path):
    from icarus_engine.trainers.run import train_xgb_file
    r = train_xgb_file(_pattern_csv(tmp_path / "NQ.csv"), "minutes", "ohlc", "NQ", out=tmp_path / "x.json",
                       ledger=tmp_path / "l.sqlite3")
    sig = r["significance"]
    assert sig["alpha"] == 0.05 and sig["vs_logit"]["p"] < 0.05 and sig["vs_null"]["p"] < 0.05
    assert sig["method"] == "paired per-row log loss, one-sided, Newey-West"


# ---- B5, B7, B10, B12: fail closed at the edges ------------------------------------------------------------

def test_a_file_with_no_usable_rows_is_blocked(tmp_path):
    from icarus_engine.trainers.run import train_xgb_file
    p = tmp_path / "naive.csv"
    p.write_text("time,open,high,low,close\n" + "\n".join(f"2024-01-02 09:{i:02d}:00,1,1,1,1" for i in range(50)) + "\n")
    r = train_xgb_file(p, "minutes", "ohlc", "NQ", out=tmp_path / "x.json", ledger=tmp_path / "l.sqlite3")
    assert r["status"] == "blocked" and r["execution_authorized"] is False


def test_offsets_without_a_colon_parse_on_this_python():
    from icarus_engine.trainers.integrity import canonical_ts
    assert canonical_ts("2023-11-14T17:13:20-0500") is not None
    assert canonical_ts("2023-11-14T17:13:20-0500") == canonical_ts("2023-11-14T22:13:20Z")


def test_a_malformed_rank_claim_is_rejected_not_raised(tmp_path):
    from icarus_engine.trainers.qualify import qualify_rank
    p = tmp_path / "NQ_clock_minutes_rank.json"
    from icarus_engine.trainers.rank_slot import RANK_KEYS, SCHEMA
    p.write_text(json.dumps({"schema": SCHEMA, "slot": "rank", "status": "fitted", "symbol": "NQ",
                             "family": "clock_minutes", "features": list(RANK_KEYS), "execution_authorized": False,
                             "baseline": {}, "holdout_claim": {"status": "NEW", "ledger": 7, "hold_start_ts": None},
                             "rows_sha256": "0" * 64}))
    assert qualify_rank(p, "NQ", "clock_minutes", [])[0].startswith("BLOCKED_")


def test_trainer_cli_rejects_a_candidate_without_a_name(tmp_path, capsys):
    from icarus_engine.trainers.__main__ import main
    with pytest.raises(SystemExit) as done:
        main(["--slot", "rank", "--path", "x.csv", "--chart-type", "minutes", "--asset", "NQ", "--cand", "noequals.csv"])
    assert done.value.code == 2


def test_trainer_cli_reports_a_monthly_chart_instead_of_a_traceback(tmp_path, capsys):
    from icarus_engine.trainers.__main__ import main
    rc = main(["--path", str(_pattern_csv(tmp_path / "x.csv")), "--chart-type", "1M", "--asset", "NQ"])
    out = json.loads(capsys.readouterr().out)
    assert rc == 1 and out["status"] == "blocked" and "monthly" in out["reason"]


# ---- B6: every early rejection reads the body first ----------------------------------------------------------

def test_every_early_post_rejection_keeps_its_answer(tmp_path):
    from icarus_engine.runtime import Journal, Portfolio
    from icarus_engine.server import serve
    journal = Journal(":memory:")
    srv = serve(Portfolio(journal, str(tmp_path)), 0, "test-token", start=False)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    body = b'{"asset": "NQ"}'
    def post(path):
        conn = HTTPConnection("127.0.0.1", srv.server_port, timeout=5)
        try:
            conn.request("POST", path, body=body)
            return conn.getresponse().status
        finally:
            conn.close()
    try:
        assert [post("/admin/pause") for _ in range(400)] == [401] * 400
        assert [post("/nowhere") for _ in range(400)] == [404] * 400
    finally:
        srv.shutdown(); srv.server_close(); t.join(5); journal.con.close()


# ---- verification of #37: fail closed by default -----------------------------------------------------------

def _one_bar_per_minute_market(n=400, seed=9):
    """A range series in a quiet market: one bar per minute, stamped at the minute floor with no millisecond
    counter, so its stamps look exactly like 1-minute candles. Bar i opened somewhere in minute i and kept forming
    until bar i+1 opened, so its move overlaps execution minute i+1."""
    rng = random.Random(seed)
    m = [rng.choice((1.0, -1.0)) for _ in range(n + 2)]
    ex = [100.0]
    for i in range(1, n):
        ex.append(ex[-1] + m[i])
    cand = [100.0]
    for i in range(1, n):
        cand.append(cand[-1] + m[i + 1])
    return _bars(ex), _bars(cand)


def test_an_undeclared_candidate_is_treated_as_floored():
    ex, cand = _one_bar_per_minute_market()
    from icarus_engine.audit.lead import floored_stamps
    assert floored_stamps(cand) is False                        # nothing in the stamps gives it away
    r = score_pair(ex, cand, seed_events(), "AAPL", "NQ")
    assert r["overlap"] > 200 and 0.35 < r["sign_agree"] < 0.65


def test_the_ranker_is_fail_closed_by_default_too():
    from icarus_engine.trainers.rank_slot import rank_rows
    ex, cand = _one_bar_per_minute_market()
    rows = rank_rows(ex, {"R": cand}, [])
    assert 0.35 < sum(r["y"] > 0 for r in rows) / len(rows) < 0.65


def test_a_clock_declaration_is_overridden_by_floored_stamps():
    ex, cand = _floored_market()
    r = score_pair(ex, cand, seed_events(), "AAPL", "NQ", cand_floored=False)
    assert 0.35 < r["sign_agree"] < 0.65


def test_train_rank_file_takes_the_candidates_chart(tmp_path):
    from icarus_engine.trainers.run import train_rank_file
    ex, cand = _one_bar_per_minute_market(700)
    def write(name, bars):
        p = tmp_path / f"{name}.csv"
        p.write_text("time,open,high,low,close\n" + "\n".join(
            f"{b['ts']},{b['open']},{b['high']},{b['low']},{b['close']}" for b in bars) + "\n")
        return p
    r = train_rank_file(write("NQ", ex), "minutes", "ohlc", "NQ", {"R": write("R", cand)}, cand_chart="range",
                        out=tmp_path / "r.json", ledger=tmp_path / "l.sqlite3")
    assert r["candidate_timing"] == "minute-floored stamps"
    r = train_rank_file(write("NQ", ex), "minutes", "ohlc", "NQ", {"R": write("R", cand)}, cand_chart="1m",
                        out=tmp_path / "r2.json", ledger=tmp_path / "l2.sqlite3")
    assert r["candidate_timing"] == "exact clock stamps"


def test_a_relative_ledger_setting_is_refused(tmp_path, monkeypatch):
    from icarus_engine.trainers import ledger
    monkeypatch.setenv("ICARUS_LEDGER", "relative/ledger.sqlite3")
    with pytest.raises(ValueError, match="absolute"):
        ledger.canonical()
