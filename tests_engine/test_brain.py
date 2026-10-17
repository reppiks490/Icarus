from __future__ import annotations

import json
import errno
import multiprocessing
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from icarus_engine import brain
from icarus_engine.brain import AGENTS, SUBSYSTEMS, brain_snapshot, candidate_gate, record_brain_event


def _candidate(**overrides):
    body = {
        "kind": "candidate",
        "subject": "nq-trend-v1",
        "summary": "regime specialist candidate",
        "status": "qualified",
        "candidate_id": "nq-trend-v1",
        "stage": "qualified_shadow",
        "regimes": ["STRONG"],
        "metrics": {"validation_score": 0.81},
        "validation": {
            "causal_time": True,
            "provenance": True,
            "oos": True,
            "protected_holdout": True,
            "multiple_testing": True,
            "costs_slippage_latency": True,
            "ablation": True,
            "calibration": True,
            "ood_drift": True,
            "deterministic_replay": True,
            "independent_verification": True,
        },
        "source_repo": "reppiks490/Icarus",
        "source_commit": "a" * 40,
        "evidence": ["test evidence"],
    }
    body.update(overrides)
    return body


def test_brain_registers_five_custom_agents_and_twelve_plus_subsystems(tmp_path):
    out = brain_snapshot(tmp_path)
    assert len(AGENTS) == 5
    assert len(SUBSYSTEMS) >= 12
    assert out["architecture"]["agent_count"] == 5
    assert {"parallax", "provenance", "ml", "data", "csv-evidence-lab"} <= {x["id"] for x in out["architecture"]["subsystems"]}
    assert out["architecture"]["subsystem_count"] >= 12
    assert out["authority"]["production_decision_authorized"] is False
    assert out["authority"]["execution_authorized"] is False
    assert out["truth_contract"]["success_rate"] is None
    assert out["truth_contract"]["omnipotence_claim"] is False
    assert out["remote_sync"]["status"] == "not_configured"
    assert out["research_sync"]["status"] == "not_configured"
    assert out["evidence_lab_sync"]["status"] == "not_configured"
    assert out["evidence_lab_sync"]["execution_authorized"] is False
    assert out["performance_proof"]["metrics"]["success_rate"] is None
    assert out["latency_telemetry"]["hot_path"] is None
    assert out["evidence_tournaments"] == []
    assert out["evidence_graph"]["metrics"]["node_count"] == 0
    assert out["evidence_graph"]["execution_authorized"] is False
    assert out["source_reliability"]["observation_count"] == 0
    assert out["source_reliability"]["execution_authorized"] is False


def test_brain_surfaces_zero_cost_incubator_without_promotion_authority(tmp_path):
    research = {
        "adaptation": {
            "assets": {
                "NQ": {
                    "last_proposal": "p" * 64,
                    "review_mode": "study_only",
                    "status": "candidate_proposed",
                    "regime_context": {
                        "label": "STRONG TREND",
                        "regime_score": 0.81,
                        "observed_market_ts": 660,
                    },
                }
            }
        },
        "ledger": {
            "proposals": [
                {
                    "proposal_id": "p" * 64,
                    "state": "proposed",
                    "candidate": {
                        "asset": "NQ",
                        "inputs": {"use_cycle": False},
                        "decision_at": "2026-10-01T05:00:00Z",
                        "expires_at": "2026-10-01T06:00:00Z",
                    },
                    "reviews": [],
                },
                {
                    "proposal_id": "a" * 64,
                    "state": "approved",
                    "candidate": {
                        "asset": "GC",
                        "inputs": {"conf_min_votes": 5},
                        "decision_at": "2026-10-01T05:00:00Z",
                        "expires_at": "2026-10-01T06:00:00Z",
                    },
                    "reviews": [{"provider": "openai"}, {"provider": "anthropic"}],
                },
            ]
        }
    }
    out = brain_snapshot(tmp_path, research_status=research)
    assert out["incubator"]["available"] is True
    assert out["incubator"]["proposal_count"] == 2
    assert out["incubator"]["review_required"] == 1
    assert out["incubator"]["approved"] == 1
    nq = next(row for row in out["incubator"]["proposals"] if row["asset"] == "NQ")
    assert nq["review_mode"] == "study_only"
    assert nq["scheduler_status"] == "candidate_proposed"
    assert nq["regime_context"]["label"] == "STRONG TREND"
    assert nq["regime_context"]["regime_score"] == 0.81
    assert out["incubator"]["execution_authorized"] is False
    assert out["incubator"]["production_decision_authorized"] is False
    assert out["learning"]["incubator_proposals"] == 2
    assert out["learning"]["incubator_review_required"] == 1


def test_candidate_gate_is_fail_closed_until_every_validation_gate_passes(tmp_path):
    body = _candidate()
    rec = record_brain_event(tmp_path, body)
    assert rec["execution_authorized"] is False
    snap = brain_snapshot(
        tmp_path,
        market_status={
            "assets": [
                {"symbol": "NQ", "warm": True, "paused": False, "state": {"rate_regime_str": "STRONG", "rate_regime": 0.84}}
            ]
        },
    )
    assert snap["candidates"][0]["eligible_for_regime_swap"] is True
    assert snap["regime_routes"][0]["selected_candidate"] == "nq-trend-v1"
    assert snap["regime_routes"][0]["selection_mode"] == "SHADOW_ONLY"

    bad = dict(snap["candidates"][0])
    bad["validation"] = dict(bad["validation"])
    bad["validation"]["protected_holdout"] = False
    eligible, blockers = candidate_gate(bad)
    assert eligible is False
    assert "protected_holdout gate not verified" in blockers


def test_brain_event_is_idempotent_and_never_mints_execution_authority(tmp_path):
    first = record_brain_event(tmp_path, _candidate())
    second = record_brain_event(tmp_path, _candidate())
    assert first["idempotent"] is False
    assert second["idempotent"] is True
    assert second["event"]["execution_authorized"] is False
    assert second["event"]["production_decision_authorized"] is False


def test_candidate_requires_exact_git_provenance(tmp_path):
    body = _candidate(source_commit="short")
    try:
        record_brain_event(tmp_path, body)
    except ValueError as ex:
        assert "40-character Git SHA" in str(ex)
    else:
        raise AssertionError("candidate without exact source revision must fail")


def test_brain_surfaces_closed_sample_proof_and_tournament(tmp_path):
    proof = {
        "metrics": {"success_rate": 1.0, "outcome_coverage": 1.0, "brier_score": 0.04, "expected_calibration_error": 0.02, "matured_forecasts": 30, "settled_forecasts": 30},
        "closed_sample": {"complete": True, "historical_100_percent_established": True, "future_guarantee": False},
        "replay": {"determinism_rate": 1.0, "historical_100_percent_established": True},
        "candidate_statistics": [{
            "candidate_id": "nq-trend-v1", "asset": "NQ", "regime": "STRONG",
            "success_definition": "positive net outcome after configured costs", "horizon_seconds": 300,
            "matured": 30, "settled": 30, "successes": 30, "outcome_coverage": 1.0,
            "success_rate": 1.0, "brier_score": 0.04, "closed_regime_sample": True,
        }],
        "execution_authorized": False, "production_decision_authorized": False,
    }
    latency = {"hot_path": {"stage": "shadow_decision_total", "p99_ms": 12.5, "budget_status": "PASS_P99"}, "stages": [], "targets_are_measured_not_assumed": True, "execution_authorized": False, "production_decision_authorized": False}
    out = brain_snapshot(tmp_path, proof_status=proof, latency_status=latency)
    assert out["truth_contract"]["success_rate"] == 1.0
    assert out["truth_contract"]["success_rate_status"] == "ESTABLISHED_100_PERCENT_CLOSED_SAMPLE"
    assert out["truth_contract"]["future_guarantee"] is False
    assert out["latency_telemetry"]["hot_path"]["p99_ms"] == 12.5
    assert out["evidence_tournaments"][0]["shadow_champion"] == "nq-trend-v1"


def test_brain_registers_apex_omega_research_subsystem(tmp_path):
    out = brain_snapshot(tmp_path)
    rows = {x["id"]: x for x in SUBSYSTEMS}
    assert "apex-omega" in rows
    assert rows["apex-omega"]["owner"] == "omega"
    assert "world-state" in rows["apex-omega"]["job"].lower()
    assert "epistemic" in rows["apex-omega"]["job"].lower()
    assert out["authority"]["production_decision_authorized"] is False
    assert out["authority"]["execution_authorized"] is False


def test_brain_registers_pantheon_echo_research_subsystem(tmp_path):
    out = brain_snapshot(tmp_path)
    rows = {x["id"]: x for x in SUBSYSTEMS}
    assert "echo" in rows
    assert rows["echo"]["title"] == "ECHO Ω"
    assert rows["echo"]["owner"] == "pantheon"
    assert "evidence-ancestry" in rows["echo"]["job"].lower()
    assert "without trading authority" in rows["echo"]["job"].lower()
    surfaced = {x["id"]: x for x in out["architecture"]["subsystems"]}
    assert surfaced["echo"]["title"] == "ECHO Ω"
    assert surfaced["echo"]["status"] == "REGISTERED"
    assert out["authority"]["production_decision_authorized"] is False
    assert out["authority"]["execution_authorized"] is False


def test_brain_registers_continuous_learning_fabric(tmp_path):
    out = brain_snapshot(tmp_path)
    rows = {x["id"]: x for x in SUBSYSTEMS}
    assert "learning-fabric" in rows
    assert rows["learning-fabric"]["owner"] == "aion"
    assert "outcome" in rows["learning-fabric"]["job"].lower()
    assert "calibration" in rows["learning-fabric"]["job"].lower()
    assert "historical replay" in rows["learning-fabric"]["job"].lower()
    assert out["authority"]["execution_authorized"] is False
    assert out["authority"]["production_decision_authorized"] is False


def test_brain_registers_pantheon_lethe_research_subsystem(tmp_path):
    out = brain_snapshot(tmp_path)
    rows = {x["id"]: x for x in SUBSYSTEMS}
    assert "lethe" in rows
    assert rows["lethe"]["title"] == "LETHE Ω"
    assert rows["lethe"]["owner"] == "pantheon"
    assert "memory" in rows["lethe"]["job"].lower()
    assert "resurrection" in rows["lethe"]["job"].lower()
    surfaced = {x["id"]: x for x in out["architecture"]["subsystems"]}
    assert surfaced["lethe"]["status"] == "REGISTERED"
    assert out["authority"]["execution_authorized"] is False
    assert out["authority"]["production_decision_authorized"] is False


def test_brain_registers_ascendancy_capability_orchestrator(tmp_path):
    out = brain_snapshot(tmp_path)
    rows = {x["id"]: x for x in SUBSYSTEMS}
    assert "capability-orchestrator" in rows
    assert rows["capability-orchestrator"]["owner"] == "omega"
    assert "capability" in rows["capability-orchestrator"]["job"].lower()
    assert "evidence" in rows["capability-orchestrator"]["job"].lower()
    surfaced = {x["id"]: x for x in out["architecture"]["subsystems"]}
    assert surfaced["capability-orchestrator"]["status"] == "REGISTERED"
    assert out["authority"]["execution_authorized"] is False
    assert out["authority"]["production_decision_authorized"] is False


@pytest.mark.parametrize(("older_clock", "newer_clock"), [
    ("2026-10-10T12:30:00+03:00", "2026-10-10T10:00:00Z"),
    ("2026-10-11T00:30:00+02:00", "2026-10-10T23:00:00Z"),
    ("2026-10-10T10:00:00Z", "2026-10-10T10:00:00.000001Z"),
    ("2026-10-10T10:00:00.100000Z", "2026-10-10T10:00:00.2Z"),
])
@pytest.mark.parametrize("reverse_append", [False, True])
def test_brain_chronological_order_uses_utc_and_fractional_seconds(
    tmp_path, older_clock, newer_clock, reverse_append, brain_clock,
):
    older = _clock_event(older_clock, subject="older UTC evidence")
    newer = _clock_event(newer_clock, subject="newer UTC evidence")
    appended = [older, newer][:: -1 if reverse_append else 1]
    path = _clock_journal(tmp_path, appended)
    original = path.read_bytes()

    rows, errors = brain._read_events(tmp_path)
    snapshot = brain.brain_snapshot(tmp_path)

    assert errors == snapshot["learning"]["journal_errors"] == 0
    assert [row["id"] for row in rows] == [older["id"], newer["id"]]
    assert [row["recorded_at"] for row in rows] == [older_clock, newer_clock]
    assert [row["id"] for row in snapshot["events"]] == [older["id"], newer["id"]]
    assert path.read_bytes() == original
    assert snapshot["authority"]["execution_authorized"] is False
    assert snapshot["authority"]["production_decision_authorized"] is False


def _chronology_candidate(stage, recorded_at):
    semantic = brain._event_semantic(_candidate(
        subject="synthetic chronology candidate",
        candidate_id="synthetic-chronology-candidate",
        summary="Synthetic candidate chronology regression only",
        stage=stage,
        status="rejected" if stage == "rejected" else "qualified",
        source_repo="synthetic/chronology-fixture",
    ))
    return {**semantic, "id": brain._event_id(semantic), "recorded_at": recorded_at}


@pytest.mark.parametrize("limit", [1, 2])
@pytest.mark.parametrize("reverse_append", [False, True])
def test_brain_chronological_order_keeps_newer_rejection_and_removes_shadow_route(
    tmp_path, limit, reverse_append, brain_clock,
):
    qualified = _chronology_candidate("qualified_shadow", "2026-10-10T12:30:00+03:00")
    rejected = _chronology_candidate("rejected", "2026-10-10T10:00:00Z")
    path = _clock_journal(tmp_path, [qualified, rejected][:: -1 if reverse_append else 1])
    original = path.read_bytes()

    rows, errors = brain._read_events(tmp_path, limit=limit)
    snapshot = brain.brain_snapshot(tmp_path, limit=limit, market_status={
        "assets": [{"symbol": "SYNTHETIC", "state": {"rate_regime_str": "STRONG"}}],
    })

    assert errors == 0
    assert [row["id"] for row in rows] == [qualified["id"], rejected["id"]][-limit:]
    candidate = brain._latest_candidates(rows)[0]
    assert candidate["id"] == snapshot["candidates"][0]["id"] == rejected["id"]
    assert candidate["stage"] == "rejected"
    assert candidate["eligible_for_regime_swap"] is False
    assert snapshot["regime_routes"][0]["selected_candidate"] is None
    assert snapshot["regime_routes"][0]["eligible_shadow_candidates"] == []
    assert snapshot["regime_routes"][0]["selection_mode"] == "SHADOW_ONLY"
    assert snapshot["authority"]["execution_authorized"] is False
    assert snapshot["authority"]["production_decision_authorized"] is False
    assert path.read_bytes() == original


@pytest.mark.parametrize(("first_clock", "second_clock"), [
    ("2026-10-10T14:00:00+04:00", "2026-10-10T05:00:00-05:00"),
    ("2026-10-10T10:00:00Z", "2026-10-10T10:00:00+00:00"),
    ("2026-10-10T10:00:00.000000Z", "2026-10-10T10:00:00+00:00"),
])
@pytest.mark.parametrize("reverse_append", [False, True])
def test_brain_chronological_order_ties_equivalent_instants_by_semantic_id(
    tmp_path, first_clock, second_clock, reverse_append,
):
    expected = sorted([
        _clock_event(first_clock, subject="synthetic ID tie alpha"),
        _clock_event(first_clock, subject="synthetic ID tie beta"),
    ], key=lambda row: row["id"])
    expected[0]["recorded_at"] = first_clock
    expected[1]["recorded_at"] = second_clock
    path = _clock_journal(tmp_path, expected[:: -1 if reverse_append else 1])
    original = path.read_bytes()

    rows, errors = brain._read_events(tmp_path)

    assert errors == 0
    assert [row["id"] for row in rows] == [row["id"] for row in expected]
    assert [row["recorded_at"] for row in rows] == [first_clock, second_clock]
    assert path.read_bytes() == original


@pytest.mark.parametrize("reverse_append", [False, True])
def test_brain_chronological_order_candidate_tie_uses_maximum_semantic_id(
    tmp_path, reverse_append, brain_clock,
):
    expected = sorted([
        _chronology_candidate("qualified_shadow", "2026-10-10T10:00:00Z"),
        _chronology_candidate("rejected", "2026-10-10T10:00:00Z"),
    ], key=lambda row: row["id"])
    expected[0]["recorded_at"] = "2026-10-10T14:00:00+04:00"
    expected[1]["recorded_at"] = "2026-10-10T05:00:00-05:00"
    path = _clock_journal(tmp_path, expected[:: -1 if reverse_append else 1])
    original = path.read_bytes()

    snapshot = brain.brain_snapshot(tmp_path)

    assert [row["id"] for row in snapshot["events"]] == [row["id"] for row in expected]
    assert snapshot["candidates"][0]["id"] == expected[-1]["id"]
    assert snapshot["candidates"][0]["stage"] == expected[-1]["stage"]
    assert path.read_bytes() == original


def test_brain_chronological_order_preserves_bounded_scan_and_invalid_clock_accounting(tmp_path):
    outside_window = _clock_event("2026-10-10T23:00:00Z", subject="outside inspected tail")
    older = _clock_event("2026-10-10T12:30:00+03:00", subject="older inspected evidence")
    newer = _clock_event("2026-10-10T10:00:00Z", subject="newer inspected evidence")
    invalid_clock = _clock_event("2026-10-10T11:00:00", subject="invalid naive clock")
    path = _clock_journal(tmp_path, [outside_window, older, invalid_clock, newer, "invalid object"])
    original = path.read_bytes()

    rows, errors = brain._read_events(tmp_path, limit=2)

    assert errors == 2
    assert [row["id"] for row in rows] == [older["id"], newer["id"]]
    assert all(row["id"] != outside_window["id"] for row in rows)
    assert path.read_bytes() == original


@pytest.mark.parametrize("reverse_append", [False, True])
def test_brain_chronological_order_identical_instant_and_id_retains_append_order(
    tmp_path, reverse_append,
):
    original_event = _clock_event("2026-10-10T14:00:00+04:00")
    alternate_clock = {**original_event, "recorded_at": "2026-10-10T05:00:00-05:00"}
    appended = [original_event, alternate_clock][:: -1 if reverse_append else 1]
    path = _clock_journal(tmp_path, appended)
    original = path.read_bytes()

    rows, errors = brain._read_events(tmp_path)

    assert errors == 0
    assert [row["id"] for row in rows] == [original_event["id"]] * 2
    assert [row["recorded_at"] for row in rows] == [row["recorded_at"] for row in appended]
    assert path.read_bytes() == original


BRAIN_CLOCK_NOW = datetime(2026, 10, 10, 12, 0, tzinfo=timezone.utc)


@pytest.fixture
def brain_clock(monkeypatch):
    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return BRAIN_CLOCK_NOW.astimezone(tz) if tz is not None else BRAIN_CLOCK_NOW.replace(tzinfo=None)

    monkeypatch.setattr(brain, "datetime", Clock)


def _clock_body(subject="synthetic clock regression"):
    return {
        "kind": "learning",
        "subject": subject,
        "summary": "Synthetic journal clock integrity fixture",
        "status": "observed",
    }


def _clock_event(recorded_at, *, subject="synthetic clock regression"):
    semantic = brain._event_semantic(_clock_body(subject))
    return {**semantic, "id": brain._event_id(semantic), "recorded_at": recorded_at}


def _clock_journal(tmp_path, events):
    path = tmp_path / "audit" / "brain_events.jsonl"
    path.parent.mkdir()
    path.write_bytes("".join(json.dumps(event) + "\n" for event in events).encode("utf-8"))
    return path


@pytest.mark.parametrize("recorded_at", [
    "2026-10-10T11:00:00",
    "2026-10-10",
    "not a timestamp",
    "2026-02-30T11:00:00Z",
    "2026-10-10T11:00:00+25:00",
    "0001-01-01T00:00:00+01:00",
])
def test_stored_event_rejects_invalid_or_naive_clock(recorded_at, brain_clock):
    with pytest.raises(ValueError, match="recorded_at"):
        brain._stored_event(_clock_event(recorded_at))


@pytest.mark.parametrize("recorded_at", [
    "2026-10-10T11:00:00",
    "2026-10-10",
    "not a timestamp",
    "2026-02-30T11:00:00Z",
    "0001-01-01T00:00:00+01:00",
])
def test_snapshot_accounts_for_invalid_clock_without_crashing_or_rewriting(tmp_path, recorded_at, brain_clock):
    valid = _clock_event("2026-10-10T11:30:00Z", subject="valid evidence retained")
    path = _clock_journal(tmp_path, [_clock_event(recorded_at), valid])
    original = path.read_bytes()

    snapshot = brain.brain_snapshot(tmp_path)

    assert snapshot["learning"]["journal_errors"] == 1
    assert snapshot["learning"]["brain_events_total"] == 1
    assert snapshot["learning"]["brain_events_last_hour"] == 1
    assert snapshot["learning"]["brain_events_last_24h"] == 1
    assert [row["id"] for row in snapshot["events"]] == [valid["id"]]
    assert path.read_bytes() == original
    assert snapshot["authority"]["execution_authorized"] is False
    assert snapshot["authority"]["production_decision_authorized"] is False


@pytest.mark.parametrize("recorded_at", [
    "2026-10-10T11:30:00Z",
    "2026-10-10T14:30:00+03:00",
    "2026-10-10T07:30:00-04:00",
])
def test_equivalent_aware_offsets_have_identical_counts_and_preserve_text(tmp_path, recorded_at, brain_clock):
    event = _clock_event(recorded_at)
    path = _clock_journal(tmp_path, [event])
    original = path.read_bytes()

    snapshot = brain.brain_snapshot(tmp_path)

    assert snapshot["learning"]["journal_errors"] == 0
    assert snapshot["learning"]["brain_events_last_hour"] == 1
    assert snapshot["learning"]["brain_events_last_24h"] == 1
    assert snapshot["events"][0]["recorded_at"] == recorded_at
    assert snapshot["events"][0]["id"] == event["id"]
    assert path.read_bytes() == original


@pytest.mark.parametrize(("age_seconds", "hour_count", "day_count"), [
    (-86400, 0, 0),
    (-0.000001, 0, 0),
    (0, 1, 1),
    (3599.999999, 1, 1),
    (3600, 1, 1),
    (3600.000001, 0, 1),
    (86399.999999, 0, 1),
    (86400, 0, 1),
    (86400.000001, 0, 0),
    (365 * 86400, 0, 0),
])
def test_recent_activity_windows_exclude_future_events_and_include_exact_boundaries(
    tmp_path, age_seconds, hour_count, day_count, brain_clock,
):
    event = _clock_event((BRAIN_CLOCK_NOW - timedelta(seconds=age_seconds)).isoformat())
    path = _clock_journal(tmp_path, [event])
    original = path.read_bytes()

    snapshot = brain.brain_snapshot(tmp_path)

    assert snapshot["learning"]["brain_events_total"] == 1
    assert snapshot["learning"]["journal_errors"] == 0
    assert snapshot["learning"]["brain_events_last_hour"] == hour_count
    assert snapshot["learning"]["brain_events_last_24h"] == day_count
    assert snapshot["events"][0]["id"] == event["id"]
    assert path.read_bytes() == original


def test_dedup_readback_preserves_valid_original_clock_identity_and_journal_bytes(tmp_path, brain_clock):
    event = _clock_event("2026-10-08T17:45:30.123456-04:00")
    path = _clock_journal(tmp_path, [event])
    original = path.read_bytes()

    result = brain.record_brain_event(tmp_path, _clock_body())

    assert result["idempotent"] is True
    assert result["event"]["id"] == event["id"]
    assert result["event"]["recorded_at"] == event["recorded_at"]
    assert result["execution_authorized"] is False
    assert result["production_decision_authorized"] is False
    assert path.read_bytes() == original


def test_dedup_invalid_stored_clock_fails_without_appending_or_rewriting(tmp_path, brain_clock):
    path = _clock_journal(tmp_path, [_clock_event("2026-10-10T11:00:00")])
    original = path.read_bytes()

    with pytest.raises(ValueError, match="recorded_at"):
        brain.record_brain_event(tmp_path, _clock_body())

    assert path.read_bytes() == original


# Targets stay at module scope so these exercise independent interpreters on
# both Linux and Windows instead of inheriting the parent's thread lock.
def _process_brain_writer(base_dir, body, output, *, label="writer", phase=None,
                          release=None, report_contention=False, start=None):
    from icarus_engine import brain as child_brain

    def report(kind, **fields):
        output.put({"label": label, "kind": kind, **fields})

    if phase in {"scan", "exception"}:
        real_loads = child_brain.json.loads
        gated = False

        def gated_loads(value, *args, **kwargs):
            nonlocal gated
            if not gated:
                gated = True
                if phase == "exception":
                    raise RuntimeError("synthetic scan failure")
                report("gated")
                if not release.poll(15):
                    raise TimeoutError("parent did not release journal scan")
                release.recv()
            return real_loads(value, *args, **kwargs)

        child_brain.json.loads = gated_loads
    if phase in {"fsync", "after_fsync"}:
        real_fsync = child_brain.os.fsync
        journal = Path(base_dir) / "audit" / "brain_events.jsonl"

        def gated_fsync(descriptor):
            stat = os.fstat(descriptor)
            current = journal.stat()
            if (stat.st_dev, stat.st_ino) == (current.st_dev, current.st_ino):
                if phase == "after_fsync":
                    real_fsync(descriptor)
                    os._exit(17)
                report("gated")
                if not release.poll(15):
                    raise TimeoutError("parent did not release journal fsync")
                release.recv()
            return real_fsync(descriptor)

        child_brain.os.fsync = gated_fsync
    if report_contention:
        sent = False
        if os.name == "nt":
            import msvcrt
            module, attribute = msvcrt, "locking"
        else:
            import fcntl
            module, attribute = fcntl, "flock"
        real_lock = getattr(module, attribute)

        def observed_lock(*args):
            nonlocal sent
            try:
                return real_lock(*args)
            except OSError as error:
                if error.errno in {errno.EACCES, errno.EAGAIN} and not sent:
                    sent = True
                    report("contended")
                raise

        setattr(module, attribute, observed_lock)
    try:
        if start is not None:
            report("ready")
            if not start.wait(15):
                raise TimeoutError("parent did not start journal writer")
        result = child_brain.record_brain_event(base_dir, body)
        report("result", result=result)
    except BaseException as error:
        report("error", error=type(error).__name__, message=str(error))


def _stop_brain_processes(processes, output, release=None):
    if release is not None:
        try:
            release.send(None)
        except (BrokenPipeError, OSError):
            pass
    for process in processes:
        if process.pid is not None:
            process.join(2)
            if process.is_alive():
                process.terminate()
                process.join(5)
    output.close()
    output.join_thread()


@pytest.mark.parametrize("phase", ["scan", "fsync"])
def test_process_duplicate_waits_for_full_scan_append_and_fsync(tmp_path, phase):
    context = multiprocessing.get_context("spawn")
    output = context.Queue()
    waiting, release = context.Pipe(duplex=False)
    path = _clock_journal(tmp_path, [_clock_event("2026-10-08T12:00:00Z", subject="prior history")])
    original = path.read_bytes()
    body = _clock_body(subject="process duplicate")
    first = context.Process(target=_process_brain_writer, args=(str(tmp_path), body, output),
                            kwargs={"label": "first", "phase": phase, "release": waiting})
    second = context.Process(target=_process_brain_writer, args=(str(tmp_path), body, output),
                             kwargs={"label": "second", "report_contention": True})
    try:
        first.start()
        assert output.get(timeout=15) == {"label": "first", "kind": "gated"}
        second.start()
        assert output.get(timeout=15) == {"label": "second", "kind": "contended"}
        release.send(None)
        results = [output.get(timeout=15) for _ in range(2)]
        assert all(row["kind"] == "result" for row in results), results
        answers = [row["result"] for row in results]
        assert sorted(row["idempotent"] for row in answers) == [False, True]
        assert answers[0]["event"] == answers[1]["event"]
        assert all(row["execution_authorized"] is False and row["production_decision_authorized"] is False
                   for row in answers)
        rows = [brain._stored_event(json.loads(line)) for line in path.read_text().splitlines()]
        assert len(rows) == 2
        assert path.read_bytes().startswith(original)
        assert len({row["id"] for row in rows}) == 2
        for process in (first, second):
            process.join(10)
            assert process.exitcode == 0
    finally:
        _stop_brain_processes((first, second), output, release)
        waiting.close()
        release.close()


def test_spawned_distinct_events_preserve_all_rows_and_history(tmp_path):
    context = multiprocessing.get_context("spawn")
    output, start = context.Queue(), context.Event()
    path = _clock_journal(tmp_path, [_clock_event("2026-10-08T12:00:00Z", subject="prior history")])
    original = path.read_bytes()
    bodies = [{**_clock_body(subject=f"distinct process {index}"), "details": {"payload": "x" * 20000}}
              for index in range(4)]
    processes = [context.Process(target=_process_brain_writer, args=(str(tmp_path), body, output),
                                 kwargs={"label": str(index), "start": start})
                 for index, body in enumerate(bodies)]
    try:
        for process in processes:
            process.start()
        ready = [output.get(timeout=15) for _ in processes]
        assert all(row["kind"] == "ready" for row in ready), ready
        start.set()
        results = [output.get(timeout=15) for _ in processes]
        assert all(row["kind"] == "result" and row["result"]["idempotent"] is False
                   for row in results), results
        rows = [brain._stored_event(json.loads(line)) for line in path.read_text().splitlines()]
        assert len(rows) == 5
        assert len({row["id"] for row in rows}) == 5
        assert {row["subject"] for row in rows[1:]} == {body["subject"] for body in bodies}
        assert all(row["execution_authorized"] is False and row["production_decision_authorized"] is False
                   for row in rows)
        assert path.read_bytes().startswith(original)
        for process in processes:
            process.join(10)
            assert process.exitcode == 0
    finally:
        start.set()
        _stop_brain_processes(processes, output)


@pytest.mark.parametrize("phase", ["exception", "scan"])
def test_process_exception_or_termination_releases_persistent_lock(tmp_path, phase):
    context = multiprocessing.get_context("spawn")
    output = context.Queue()
    waiting, release = context.Pipe(duplex=False)
    path = _clock_journal(tmp_path, [_clock_event("2026-10-08T12:00:00Z", subject="prior history")])
    original = path.read_bytes()
    lock_path = path.with_name(path.name + ".lock")
    body = _clock_body(subject="failed process")
    process = context.Process(target=_process_brain_writer, args=(str(tmp_path), body, output),
                              kwargs={"phase": phase, "release": waiting})
    try:
        process.start()
        observed = output.get(timeout=15)
        assert observed["kind"] == ("error" if phase == "exception" else "gated"), observed
        if phase == "scan":
            process.terminate()
        process.join(10)
        assert not process.is_alive()
        assert path.read_bytes() == original
        identity = lock_path.stat()
        response = brain.record_brain_event(tmp_path, body)
        assert response["idempotent"] is False
        assert path.read_bytes().startswith(original)
        assert (lock_path.stat().st_dev, lock_path.stat().st_ino) == (identity.st_dev, identity.st_ino)
    finally:
        _stop_brain_processes((process,), output, release)
        waiting.close()
        release.close()


def test_process_exit_after_real_fsync_retries_original_event(tmp_path):
    context = multiprocessing.get_context("spawn")
    output = context.Queue()
    body = _clock_body(subject="completed fsync before process exit")
    process = context.Process(target=_process_brain_writer, args=(str(tmp_path), body, output),
                              kwargs={"phase": "after_fsync"})
    try:
        process.start()
        process.join(15)
        assert process.exitcode == 17
        path = tmp_path / "audit" / "brain_events.jsonl"
        original = path.read_bytes()
        stored = brain._stored_event(json.loads(original))
        response = brain.record_brain_event(tmp_path, body)
        assert response["idempotent"] is True
        assert response["event"] == stored
        assert path.read_bytes() == original
    finally:
        _stop_brain_processes((process,), output)


def test_record_brain_event_rejects_symlinked_audit_directory(tmp_path):
    runtime = tmp_path / "runtime"
    outside = tmp_path / "outside"
    runtime.mkdir()
    outside.mkdir()
    audit = runtime / "audit"
    try:
        audit.symlink_to(outside, target_is_directory=True)
    except OSError as error:
        if os.name == "nt" and getattr(error, "winerror", None) == 1314:
            pytest.skip("Windows runner does not permit symlinks")
        raise

    with pytest.raises(ValueError, match="brain journal parent must be a real directory"):
        brain.record_brain_event(runtime, _clock_body())

    assert list(outside.iterdir()) == []


@pytest.mark.parametrize("component", ["brain_events.jsonl", "brain_events.jsonl.lock"])
@pytest.mark.parametrize("link_kind", ["symlink", "hardlink"])
def test_process_lock_rejects_journal_and_lock_aliases_before_writes(tmp_path, component, link_kind):
    outside = tmp_path / "outside"
    outside.write_bytes(b"must remain unchanged\n")
    original_mode = outside.stat().st_mode
    audit = tmp_path / "runtime" / "audit"
    audit.mkdir(parents=True)
    target = audit / component
    try:
        if link_kind == "symlink":
            target.symlink_to(outside)
        else:
            os.link(outside, target)
    except OSError as error:
        if os.name == "nt" and getattr(error, "winerror", None) == 1314:
            pytest.skip("Windows runner does not permit symlinks")
        raise
    with pytest.raises(ValueError, match="symlink|hard links"):
        brain.record_brain_event(audit.parent, _clock_body())
    assert outside.read_bytes() == b"must remain unchanged\n"
    assert outside.stat().st_mode == original_mode


@pytest.mark.parametrize("component", ["brain_events.jsonl", "brain_events.jsonl.lock"])
def test_process_lock_rejects_nonregular_paths_without_writing(tmp_path, component):
    audit = tmp_path / "audit"
    audit.mkdir()
    (audit / component).mkdir()
    with pytest.raises((ValueError, OSError)):
        brain.record_brain_event(tmp_path, _clock_body())
    assert (audit / component).is_dir()


@pytest.mark.skipif(os.name != "posix", reason="POSIX FIFO boundary")
@pytest.mark.parametrize("component", ["brain_events.jsonl", "brain_events.jsonl.lock"])
def test_process_lock_rejects_openable_nonregular_file_without_writing(tmp_path, component):
    audit = tmp_path / "audit"
    audit.mkdir()
    os.mkfifo(audit / component)
    with pytest.raises(ValueError, match="regular files"):
        brain.record_brain_event(tmp_path, _clock_body())


def test_unexpected_process_lock_error_does_not_write_history(tmp_path, monkeypatch):
    path = _clock_journal(tmp_path, [_clock_event("2026-10-08T12:00:00Z")])
    original = path.read_bytes()
    if os.name == "nt":
        import msvcrt
        module, attribute = msvcrt, "locking"
    else:
        import fcntl
        module, attribute = fcntl, "flock"

    def broken_lock(*args):
        raise OSError(errno.EBADF, "synthetic invalid locking descriptor")

    monkeypatch.setattr(module, attribute, broken_lock)
    with pytest.raises(OSError) as captured:
        brain.record_brain_event(tmp_path, _clock_body(subject="new event"))
    assert captured.value.errno == errno.EBADF
    assert path.read_bytes() == original


def test_process_lock_contention_timeout_does_not_write_history(tmp_path, monkeypatch):
    context = multiprocessing.get_context("spawn")
    output = context.Queue()
    waiting, release = context.Pipe(duplex=False)
    path = _clock_journal(tmp_path, [_clock_event("2026-10-08T12:00:00Z", subject="prior history")])
    original = path.read_bytes()
    process = context.Process(target=_process_brain_writer,
                              args=(str(tmp_path), _clock_body(subject="holder"), output),
                              kwargs={"phase": "scan", "release": waiting})
    try:
        process.start()
        assert output.get(timeout=15)["kind"] == "gated"
        monkeypatch.setattr(brain, "_PROCESS_LOCK_TIMEOUT_SECONDS", 0.1, raising=False)
        with pytest.raises(TimeoutError, match="busy"):
            brain.record_brain_event(tmp_path, _clock_body(subject="waiting writer"))
        assert path.read_bytes() == original
    finally:
        _stop_brain_processes((process,), output, release)
        waiting.close()
        release.close()


@pytest.mark.skipif(os.name == "nt", reason="Windows does not permit replacing these open file handles")
def test_waiter_rejects_replaced_lock_inode_before_writing(tmp_path):
    context = multiprocessing.get_context("spawn")
    output = context.Queue()
    waiting, release = context.Pipe(duplex=False)
    path = _clock_journal(tmp_path, [_clock_event("2026-10-08T12:00:00Z", subject="prior history")])
    original = path.read_bytes()
    first = context.Process(target=_process_brain_writer,
                            args=(str(tmp_path), _clock_body(subject="holder"), output),
                            kwargs={"label": "holder", "phase": "scan", "release": waiting})
    second = context.Process(target=_process_brain_writer,
                             args=(str(tmp_path), _clock_body(subject="waiter"), output),
                             kwargs={"label": "waiter", "report_contention": True})
    try:
        first.start()
        assert output.get(timeout=15)["kind"] == "gated"
        second.start()
        assert output.get(timeout=15) == {"label": "waiter", "kind": "contended"}
        lock_path = path.with_name(path.name + ".lock")
        lock_path.rename(lock_path.with_suffix(".old"))
        lock_path.write_bytes(b"0")
        release.send(None)
        observations = [output.get(timeout=15) for _ in range(2)]
        assert {row["label"]: row["kind"] for row in observations} == {"holder": "error", "waiter": "error"}
        assert path.read_bytes() == original
    finally:
        _stop_brain_processes((first, second), output, release)
        waiting.close()
        release.close()


@pytest.mark.skipif(os.name == "nt", reason="Windows does not permit replacing these open file handles")
def test_replaced_journal_inode_blocks_append_to_both_files(tmp_path):
    context = multiprocessing.get_context("spawn")
    output = context.Queue()
    waiting, release = context.Pipe(duplex=False)
    path = _clock_journal(tmp_path, [_clock_event("2026-10-08T12:00:00Z", subject="prior history")])
    original = path.read_bytes()
    process = context.Process(target=_process_brain_writer,
                              args=(str(tmp_path), _clock_body(subject="writer"), output),
                              kwargs={"phase": "scan", "release": waiting})
    try:
        process.start()
        assert output.get(timeout=15)["kind"] == "gated"
        prior = path.with_suffix(".old")
        path.rename(prior)
        replacement = b"replacement remains untouched\n"
        path.write_bytes(replacement)
        release.send(None)
        observation = output.get(timeout=15)
        assert observation["kind"] == "error", observation
        assert "changed while open" in observation["message"]
        assert prior.read_bytes() == original
        assert path.read_bytes() == replacement
    finally:
        _stop_brain_processes((process,), output, release)
        waiting.close()
        release.close()


@pytest.mark.parametrize("tail", [b'{"interrupted":', b'{"complete_json":true}', b'{"complete_json":true}\r'])
def test_unterminated_tail_blocks_new_append_without_repair(tmp_path, tail):
    path = tmp_path / "audit" / "brain_events.jsonl"
    path.parent.mkdir()
    path.write_bytes(tail)
    with pytest.raises(ValueError, match="unterminated"):
        brain.record_brain_event(tmp_path, _clock_body())
    assert path.read_bytes() == tail


def test_complete_malformed_historical_line_is_preserved_when_appending(tmp_path):
    path = tmp_path / "audit" / "brain_events.jsonl"
    path.parent.mkdir()
    original = b"historical invalid JSON remains evidence\n"
    path.write_bytes(original)
    response = brain.record_brain_event(tmp_path, _clock_body())
    assert response["idempotent"] is False
    assert path.read_bytes().startswith(original)
    assert len(path.read_text().splitlines()) == 2


def test_existing_crlf_history_remains_exact_and_new_append_is_lf_framed(tmp_path):
    path = _clock_journal(tmp_path, [_clock_event("2026-10-08T12:00:00Z", subject="prior history")])
    original = path.read_bytes().replace(b"\n", b"\r\n")
    path.write_bytes(original)
    brain.record_brain_event(tmp_path, _clock_body(subject="new record"))
    raw = path.read_bytes()
    assert raw.startswith(original)
    assert raw[len(original):].endswith(b"\n")
    assert not raw[len(original):].endswith(b"\r\n")
    assert len([brain._stored_event(json.loads(line)) for line in raw.splitlines()]) == 2


@pytest.mark.skipif(os.name != "posix", reason="POSIX modes do not establish Windows ACLs")
def test_process_lock_sidecar_is_private_at_creation_under_permissive_umask(tmp_path):
    previous = os.umask(0)
    try:
        brain.record_brain_event(tmp_path, _clock_body())
    finally:
        os.umask(previous)
    assert (tmp_path / "audit" / "brain_events.jsonl.lock").stat().st_mode & 0o077 == 0
