# Claude (Opus 5.5) — 2026-09-27. SPEC.md slots 2-4. Slot 2 ranks candidates from their earlier strict-lead
# pairs only; slots 3 and 4 have data gates but no model in the spec, so they never invent one.
import json
import random

from icarus_engine.trainers.ledger import claim_holdout

T0 = 1_700_000_000
EMPTY = []


def _bars(closes, step=60, **cols):
    out = []
    for i, c in enumerate(closes):
        o = closes[i - 1] if i else c
        out.append({"ts": T0 + i * step, "open": o, "high": max(o, c) + 0.1, "low": min(o, c) - 0.1,
                    "close": c, "tide_long": 0.0, "tide_short": 0.0, **cols})
    return out


def _market(n=1200, seed=4):
    rng = random.Random(seed)
    moves = [rng.choice((1.0, -1.0)) for _ in range(n)]
    lead, ex = [100.0], [100.0, 100.0]
    for m in moves[1:]:
        lead.append(lead[-1] + m)      # the leader's bar k moves by m ...
        ex.append(ex[-1] + m)          # ... and the execution bar k+1 follows
    noise = [100.0]
    for _ in moves[1:]:
        noise.append(noise[-1] + rng.choice((1.0, -1.0)))
    return _bars(ex), {"LEAD": _bars(lead), "NOISE": _bars(noise)}


def _rated_market(n=1500, seed=4, rates=(0.7, 0.3)):
    """Candidates that agree with the next execution move at a fixed rate each: stable, but noisy over 20 pairs."""
    rng = random.Random(seed)
    moves = [rng.choice((1.0, -1.0)) for _ in range(n)]
    ex = [100.0, 100.0]
    for m in moves[1:]:
        ex.append(ex[-1] + m)
    cands = {}
    for j, rate in enumerate(rates):
        c = [100.0]
        for m in moves[1:]:
            c.append(c[-1] + (m if rng.random() < rate else -m))
        cands[f"C{j}"] = _bars(c)
    return _bars(ex), cands


# ---- slot 2: rows ----
# The synthetic markets are exact 1-minute clock bars, so they declare floored=False.-------------------------------------------------------------------------------

def test_rank_target_is_agreement_with_the_next_execution_move():
    from icarus_engine.trainers.rank_slot import rank_rows
    ex, cands = _market(300)
    rows = rank_rows(ex, {"LEAD": cands["LEAD"]}, EMPTY, floored=False)
    assert len(rows) > 250 and all(r["y"] == 1 for r in rows)


def test_rank_inputs_start_from_a_neutral_prior():
    from icarus_engine.trainers.rank_slot import RANK_KEYS, rank_rows
    ex, cands = _market(300)
    first = rank_rows(ex, {"LEAD": cands["LEAD"]}, EMPTY, floored=False)[0]
    assert list(first["x"]) == list(RANK_KEYS)
    assert first["x"] == {"sign_agree": 0.5, "tide_agree": 0.5, "macro_agree": 0.5, "overlap": 0.0}


def test_a_rows_own_outcome_never_enters_its_inputs():
    from icarus_engine.trainers.rank_slot import rank_rows
    ex, cands = _market(300)
    base = rank_rows(ex, {"NOISE": cands["NOISE"]}, EMPTY, floored=False)
    j = 120
    at = next(i for i, b in enumerate(ex) if b["ts"] == base[j]["label_ts"])
    flipped = [dict(b) for b in ex]
    delta = 2 * (flipped[at - 1]["close"] - flipped[at]["close"])
    for b in flipped[at:]:
        b["close"] += delta                   # reverses execution move `at`, keeps every other move
    moved = rank_rows(flipped, {"NOISE": cands["NOISE"]}, EMPTY, floored=False)
    assert moved[j]["y"] == -base[j]["y"]
    assert moved[j]["x"] == base[j]["x"]
    assert all(moved[i] == base[i] for i in range(j))


def test_pooled_rows_are_time_ordered_and_purged_at_slice_edges():
    from icarus_engine.trainers.dataset import purged_slices
    from icarus_engine.trainers.rank_slot import rank_rows
    ex, cands = _market()
    rows = rank_rows(ex, cands, EMPTY, floored=False)
    assert [r["ts"] for r in rows] == sorted(r["ts"] for r in rows)
    train, valid, hold = purged_slices(rows)
    assert max(r["label_ts"] for r in train) < valid[0]["ts"]
    assert max(r["label_ts"] for r in valid) < hold[0]["ts"]
    assert max(r["ts"] for r in train) < valid[0]["ts"] and max(r["ts"] for r in valid) < hold[0]["ts"]


# ---- slot 2: training, ledger, replay ---------------------------------------------------------------

def _train(tmp_path, rows):
    from icarus_engine.trainers import rank_slot
    out = tmp_path / "NQ_clock_minutes_rank.json"
    return rank_slot.train(rows, "NQ", "clock_minutes", out_path=out, ledger_path=tmp_path / "l.sqlite3"), out


def test_ranker_beats_both_baselines_on_stable_but_noisy_candidates(tmp_path):
    from icarus_engine.trainers.rank_slot import RANK_KEYS, rank_rows
    ex, cands = _rated_market()
    r, out = _train(tmp_path, rank_rows(ex, cands, EMPTY, floored=False))
    assert r["status"] == "fitted" and r["slot"] == "rank" and r["features"] == list(RANK_KEYS)
    assert r["holdout_logloss"] < r["baseline"]["null_logloss"]
    assert r["holdout_logloss"] < r["baseline"]["naive_logloss"]
    assert r["incremental_value_status"] == "PASS" and r["holdout_claim"]["status"] == "NEW"
    assert r["execution_authorized"] is False and json.loads(out.read_text()) == r


def test_gate_refuses_a_ranker_that_the_naive_trailing_rate_beats(tmp_path):
    from icarus_engine.trainers.qualify import qualify_rank
    from icarus_engine.trainers.rank_slot import rank_rows
    ex, cands = _market()                      # a perfect leader: the raw trailing rate is already near-optimal
    rows = rank_rows(ex, cands, EMPTY, floored=False)
    r, out = _train(tmp_path, rows)
    assert r["holdout_logloss"] < r["baseline"]["null_logloss"]
    assert r["holdout_logloss"] >= r["baseline"]["naive_logloss"] and r["incremental_value_status"] == "FAIL"
    assert qualify_rank(out, "NQ", "clock_minutes", rows, ledger_path=tmp_path / "l.sqlite3")[0] == "BLOCKED_BASELINE_NOT_BEATEN"


def test_rank_and_xgb_claims_live_in_separate_slots(tmp_path):
    db = tmp_path / "l.sqlite3"
    assert claim_holdout(db, "NQ", "clock_minutes", 1, 2, "r1", "s1", 5) == "NEW"
    assert claim_holdout(db, "NQ", "clock_minutes", 1, 2, "r2", "s2", 5, slot="rank") == "NEW"
    assert claim_holdout(db, "NQ", "clock_minutes", 1, 2, "r3", "s3", 5, slot="rank") == "BLOCKED_HOLDOUT_REUSE"


def test_a_point_estimate_win_without_significance_does_not_qualify(tmp_path):
    from icarus_engine.trainers.qualify import qualify_rank
    from icarus_engine.trainers.rank_slot import rank_rows
    ex, cands = _rated_market()                  # beats the naive rate on the point estimate only (p ~ 0.10)
    rows = rank_rows(ex, cands, EMPTY, floored=False)
    r, out = _train(tmp_path, rows)
    assert r["incremental_value_status"] == "PASS" and r["significance"]["significant"] is False
    assert qualify_rank(out, "NQ", "clock_minutes", rows, ledger_path=tmp_path / "l.sqlite3")[0] ==         "BLOCKED_BASELINE_NOT_BEATEN"


def test_rank_artifact_replays_from_the_rows(tmp_path):
    from icarus_engine.trainers.qualify import qualify_rank
    from icarus_engine.trainers.rank_slot import rank_rows
    ex, cands = _rated_market(n=3000, rates=(0.75, 0.25))    # enough data for the gain to be significant
    rows = rank_rows(ex, cands, EMPTY, floored=False)
    r, out = _train(tmp_path, rows)
    assert r["significance"]["significant"] is True
    assert qualify_rank(out, "NQ", "clock_minutes", rows, ledger_path=tmp_path / "l.sqlite3")[0] == "VALID_RANKER"
    assert qualify_rank(out, "NQ", "clock_minutes", None, ledger_path=tmp_path / "l.sqlite3")[0] == "UNKNOWN"
    assert qualify_rank(out, "ES", "clock_minutes", rows, ledger_path=tmp_path / "l.sqlite3")[0] == "BLOCKED_IDENTITY_MISMATCH"
    assert qualify_rank(out, "NQ", "clock_minutes", rows[:-5], ledger_path=tmp_path / "l.sqlite3")[0] == "BLOCKED_IDENTITY_MISMATCH"
    d = json.loads(out.read_text())
    out.write_text(json.dumps(dict(d, holdout_logloss=d["holdout_logloss"] * 0.9)))
    assert qualify_rank(out, "NQ", "clock_minutes", rows, ledger_path=tmp_path / "l.sqlite3")[0] == "BLOCKED_PROVENANCE"
    out.write_text(json.dumps(dict(d, execution_authorized=True)))
    assert qualify_rank(out, "NQ", "clock_minutes", rows, ledger_path=tmp_path / "l.sqlite3")[0] == "BLOCKED_EXECUTION_AUTHORITY"


def test_rank_cli_trains_from_files(tmp_path):
    from icarus_engine.trainers.__main__ import main
    ex, cands = _market(700)
    def write(name, bars):
        p = tmp_path / f"{name}.csv"
        p.write_text("time,open,high,low,close\n" + "\n".join(
            f"{b['ts']},{b['open']},{b['high']},{b['low']},{b['close']}" for b in bars) + "\n")
        return p
    out = tmp_path / "NQ_clock_minutes_rank.json"
    rc = main(["--slot", "rank", "--path", str(write("NQ", ex)), "--chart-type", "minutes", "--asset", "NQ",
               "--cand", f"LEAD={write('LEAD', cands['LEAD'])}", "--cand", f"NOISE={write('NOISE', cands['NOISE'])}",
               "--out", str(out), "--ledger", str(tmp_path / "l.sqlite3")])
    r = json.loads(out.read_text())
    assert rc == 0 and r["candidates"] == ["LEAD", "NOISE"] and r["execution_authorized"] is False


# ---- slots 3 and 4: gates only -----------------------------------------------------------------------

def _csv(tmp_path, header, n=50):
    p = tmp_path / "x.csv"
    cols = header.split(",")
    p.write_text(header + "\n" + "\n".join(",".join(str(T0 + i) if c == "time" else "1" for c in cols)
                                          for i in range(n)) + "\n")
    return p


def test_regime_skips_without_a_vol_or_rate_series(tmp_path):
    from icarus_engine.trainers.regime_slot import train
    r = train(_csv(tmp_path, "time,open,high,low,close,Volume"), "NQ")
    assert r["status"] == "skipped" and r["slot"] == "regime" and r["execution_authorized"] is False


def test_regime_with_a_series_waits_for_the_owner_to_define_the_model(tmp_path):
    from icarus_engine.trainers.regime_slot import train
    r = train(_csv(tmp_path, "time,open,high,low,close,RATE"), "NQ")
    assert r["status"] == "blocked" and r["series"] == ["RATE"] and "owner" in r["reason"]
    assert r["execution_authorized"] is False


def test_fail_slot_needs_thirty_losers_then_waits_for_the_owner(tmp_path):
    from icarus_engine.trainers.fail_slot import train
    def journal(n):
        p = tmp_path / f"j{n}.csv"
        p.write_text("symbol,pnl,exit_ts,side\n" + "\n".join(f"NQ,-1,{T0 + i},long" for i in range(n)) + "\n")
        return p
    few = train(journal(29), "NQ")
    many = train(journal(30), "NQ")
    assert few["status"] == "skipped" and few["n_losers"] == 29 and few["execution_authorized"] is False
    assert many["status"] == "blocked" and "owner" in many["reason"] and many["execution_authorized"] is False
