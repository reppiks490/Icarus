from __future__ import annotations

import importlib.util
import subprocess
import json
import sqlite3
import threading
from pathlib import Path

import pytest

from icarus_engine.ascendancy.evaluator import EvaluatorCascade
from tests_engine.test_ascendancy_evaluator import _candidate, _receipt


@pytest.fixture
def source_checkout(tmp_path):
    repo = tmp_path / "source"
    repo.mkdir()
    def git(*args):
        return subprocess.check_output(["git", "-C", str(repo), *args], text=True).strip()
    git("init", "-q")
    git("config", "user.name", "fixture")
    git("config", "user.email", "fixture@example.invalid")
    git("remote", "add", "origin", "https://github.com/reppiks490/Icarus.git")
    (repo / "README.md").write_text("contract fixture\n")
    git("add", "README.md")
    git("commit", "-qm", "fixture")
    return repo, git("rev-parse", "HEAD")


def validator(base, cascade, source):
    name = "icarus_engine.ascendancy.native_validation"
    assert importlib.util.find_spec(name) is not None, "native validator is not connected"
    from icarus_engine.ascendancy.native_validation import NativeContractValidator
    return NativeContractValidator(base, evaluator=cascade, checkout_root=source)


def test_native_contract_runs_real_worker_once_and_stops_at_smoke(tmp_path, source_checkout):
    source, commit = source_checkout
    cascade = EvaluatorCascade(tmp_path)
    candidate = _candidate(source_commit=commit)
    cascade.register_candidate(candidate)
    runner = validator(tmp_path, cascade, source)
    batch = runner.run_once()
    assert batch["submitted_count"] == 1
    current = cascade.candidate(candidate["candidate_id"])
    assert current["next_stage"] == "SMOKE_NULLS"
    assert current["resource_used"]["evaluations"] == 1
    report = runner.snapshot()["runs"][0]
    assert report["outcome"] == "PASS"
    assert report["metrics"]["scientific_performance_evaluated"] is False
    assert report["resource_usage"]["wall_seconds"] > 0
    assert report["execution_authorized"] is False
    restarted = validator(tmp_path, cascade, source)
    assert restarted.run_once()["submitted_count"] == 0
    assert cascade.snapshot()["receipt_count"] == 1
    assert restarted.snapshot()["run_count"] == 1


@pytest.mark.parametrize("revision,observations", [
    ("f" * 40, [{"name": "price", "evidence_class": "observed"}]),
    (None, [{"name": "depth", "evidence_class": "unavailable"}]),
])
def test_unverified_revision_or_unavailable_observation_is_inconclusive(
    tmp_path, source_checkout, revision, observations,
):
    source, commit = source_checkout
    cascade = EvaluatorCascade(tmp_path)
    candidate = _candidate(source_commit=revision or commit, required_observations=observations)
    cascade.register_candidate(candidate)
    runner = validator(tmp_path, cascade, source)
    runner.run_once()
    assert runner.snapshot()["runs"][0]["outcome"] == "INCONCLUSIVE"
    assert cascade.candidate(candidate["candidate_id"])["next_stage"] == "CONTRACT_VALIDATION"
    runner.run_once()
    assert cascade.snapshot()["receipt_count"] == 1


@pytest.mark.parametrize("advance", [1, 6])
def test_validator_never_runs_later_or_protected_stage(tmp_path, source_checkout, advance):
    from icarus_engine.ascendancy.evaluator import evaluation_stage_catalog
    source, commit = source_checkout
    cascade = EvaluatorCascade(tmp_path)
    candidate = _candidate(source_commit=commit)
    cascade.register_candidate(candidate)
    for stage in evaluation_stage_catalog()[:advance]:
        cascade.record(_receipt(candidate, stage["id"]))
    runner = validator(tmp_path, cascade, source)
    assert runner.run_once()["submitted_count"] == 0
    assert runner.snapshot()["run_count"] == 0
    assert cascade.snapshot()["receipt_count"] == advance


def test_pending_result_resumes_submission_without_reexecution(tmp_path, source_checkout, monkeypatch):
    source, commit = source_checkout
    cascade = EvaluatorCascade(tmp_path)
    cascade.register_candidate(_candidate(source_commit=commit))
    runner = validator(tmp_path, cascade, source)
    def outage(body):
        raise RuntimeError("submission interrupted")
    with monkeypatch.context() as patch:
        patch.setattr(cascade, "record", outage)
        with pytest.raises(RuntimeError, match="submission interrupted"):
            runner.run_once()
    report = runner.snapshot()["runs"][0]
    assert report["submission_state"] == "PENDING"
    restarted = validator(tmp_path, cascade, source)
    batch = restarted.run_once()
    assert batch["submitted_count"] == 1
    assert batch["attempted_count"] == 0
    assert restarted.snapshot()["runs"][0]["resource_usage"] == report["resource_usage"]
    assert cascade.snapshot()["receipt_count"] == 1


def test_corrupted_pending_result_cannot_create_evaluator_receipt(tmp_path, source_checkout, monkeypatch):
    source, commit = source_checkout
    cascade = EvaluatorCascade(tmp_path)
    cascade.register_candidate(_candidate(source_commit=commit))
    runner = validator(tmp_path, cascade, source)
    with monkeypatch.context() as patch:
        patch.setattr(cascade, "record", lambda body: (_ for _ in ()).throw(RuntimeError("outage")))
        with pytest.raises(RuntimeError):
            runner.run_once()
    with sqlite3.connect(runner.path) as con:
        raw = con.execute("SELECT receipt_json FROM runs").fetchone()[0]
        receipt = json.loads(raw)
        receipt["outcome"] = "FAIL"
        con.execute("UPDATE runs SET receipt_json=?", (json.dumps(receipt),))
    with pytest.raises(RuntimeError, match="integrity"):
        validator(tmp_path, cascade, source).run_once()
    assert cascade.snapshot()["receipt_count"] == 0


def test_background_worker_performs_cycle_and_stops(tmp_path, source_checkout, monkeypatch):
    source, commit = source_checkout
    cascade = EvaluatorCascade(tmp_path)
    candidate = _candidate(source_commit=commit)
    cascade.register_candidate(candidate)
    accepted = threading.Event()
    real_record = cascade.record
    def observe(body):
        result = real_record(body)
        accepted.set()
        return result
    monkeypatch.setattr(cascade, "record", observe)
    runner = validator(tmp_path, cascade, source)
    runner.start()
    try:
        assert accepted.wait(10), runner.last_error
        assert cascade.candidate(candidate["candidate_id"])["next_stage"] == "SMOKE_NULLS"
    finally:
        runner.close()
    assert not runner.snapshot()["worker_running"]


def test_exhausted_budget_does_not_launch_worker(tmp_path, source_checkout):
    source, commit = source_checkout
    cascade = EvaluatorCascade(tmp_path)
    candidate = _candidate(source_commit=commit, resource_budget={
        "max_evaluations": 1, "max_wall_seconds": 900, "max_cost_units": 10.0})
    cascade.register_candidate(candidate)
    cascade.record(_receipt(candidate, "CONTRACT_VALIDATION", outcome="INCONCLUSIVE"))
    runner = validator(tmp_path, cascade, source)
    assert runner.run_once()["attempted_count"] == 0
    assert runner.snapshot()["run_count"] == 0


def test_concurrent_cycles_share_one_durable_attempt(tmp_path, source_checkout):
    from concurrent.futures import ThreadPoolExecutor
    source, commit = source_checkout
    cascade = EvaluatorCascade(tmp_path)
    cascade.register_candidate(_candidate(source_commit=commit))
    runners = [validator(tmp_path, cascade, source) for _ in range(2)]
    with ThreadPoolExecutor(max_workers=2) as pool:
        batches = list(pool.map(lambda runner: runner.run_once(), runners))
    assert sum(batch["attempted_count"] for batch in batches) == 1
    assert cascade.snapshot()["receipt_count"] == 1
    assert runners[0].snapshot()["run_count"] == 1


def test_foreign_remote_cannot_pass_local_revision_check(tmp_path, source_checkout):
    source, commit = source_checkout
    subprocess.check_call(["git", "-C", str(source), "remote", "set-url", "origin", "https://github.com/other/repo.git"])
    cascade = EvaluatorCascade(tmp_path)
    cascade.register_candidate(_candidate(source_commit=commit))
    runner = validator(tmp_path, cascade, source)
    runner.run_once()
    report = runner.snapshot()["runs"][0]
    assert report["outcome"] == "INCONCLUSIVE"
    assert report["metrics"]["source_check"]["local_remote_matches_declared_repo"] is False


def test_blocked_receipt_cannot_starve_pending_recovery(tmp_path, source_checkout):
    from unittest.mock import patch
    source, commit = source_checkout
    cascade = EvaluatorCascade(tmp_path)
    first = _candidate(source_commit=commit, title="first")
    cascade.register_candidate(first)
    runner = validator(tmp_path, cascade, source)
    runner.max_candidates = 1
    def outage(body):
        raise RuntimeError("submission outage")
    with patch.object(cascade, "record", outage):
        try:
            runner.run_once()
        except RuntimeError:
            pass
    cascade.record(_receipt(first, "CONTRACT_VALIDATION"))
    second = _candidate(source_commit=commit, title="second")
    cascade.register_candidate(second)
    real_record = cascade.record
    def only_second_outage(body):
        return real_record(body) if body["candidate_id"] == first["candidate_id"] else outage(body)
    with patch.object(cascade, "record", only_second_outage):
        try:
            runner.run_once()
        except RuntimeError:
            pass
    assert {row["submission_state"] for row in runner.snapshot()["runs"]} == {"BLOCKED", "PENDING"}
    restarted = validator(tmp_path, cascade, source)
    restarted.max_candidates = 1
    batch = restarted.run_once()
    assert batch["submitted_count"] == 1
    assert batch["attempted_count"] == 0
    assert cascade.candidate(second["candidate_id"])["next_stage"] == "SMOKE_NULLS"


def test_unresolved_intent_blocks_new_attempt_for_same_candidate(tmp_path, source_checkout):
    source, commit = source_checkout
    cascade = EvaluatorCascade(tmp_path)
    candidate = _candidate(source_commit=commit)
    cascade.register_candidate(candidate)
    runner = validator(tmp_path, cascade, source)
    with sqlite3.connect(runner.path) as con:
        con.execute("INSERT INTO runs(run_id,candidate_id,state,created_at) VALUES(?,?,'RUNNING',?)",
                    ("f" * 64, candidate["candidate_id"], "2026-10-03T00:00:00Z"))
    assert runner.run_once()["attempted_count"] == 0
    assert cascade.snapshot()["receipt_count"] == 0
    assert runner.snapshot()["runs"][0]["submission_state"] == "RUNNING"


def test_each_cycle_checks_bounded_fair_window(tmp_path, source_checkout):
    source, _ = source_checkout
    cascade = EvaluatorCascade(tmp_path)
    for i in range(4):
        cascade.register_candidate(_candidate(title=f"candidate {i}"))
    runner = validator(tmp_path, cascade, source)
    runner.max_candidates = 2
    for _ in range(2):
        batch = runner.run_once()
        assert batch.get("checked_count") == 2
        assert batch["attempted_count"] == 2
    assert cascade.snapshot()["receipt_count"] == 4
    assert runner.run_once()["attempted_count"] == 0


def test_timeout_is_inconclusive_with_measured_usage(tmp_path, source_checkout):
    source, commit = source_checkout
    cascade = EvaluatorCascade(tmp_path)
    candidate = _candidate(source_commit=commit)
    cascade.register_candidate(candidate)
    runner = validator(tmp_path, cascade, source)
    runner.worker_timeout = .00001
    runner.run_once()
    report = runner.snapshot()["runs"][0]
    assert report["outcome"] == "INCONCLUSIVE"
    assert "worker_error" in report["metrics"]
    assert report["resource_usage"]["wall_seconds"] > 0
    assert cascade.candidate(candidate["candidate_id"])["next_stage"] == "CONTRACT_VALIDATION"


def test_bounded_cycle_does_not_load_historical_ledger(tmp_path, source_checkout, monkeypatch):
    source, commit = source_checkout
    cascade = EvaluatorCascade(tmp_path)
    candidate = _candidate(source_commit=commit)
    cascade.register_candidate(candidate)
    monkeypatch.setattr(cascade, "snapshot", lambda: (_ for _ in ()).throw(AssertionError("unbounded ledger read")))
    assert validator(tmp_path, cascade, source).run_once()["submitted_count"] == 1


def test_corrupted_stored_candidate_id_cannot_run(tmp_path, source_checkout):
    source, commit = source_checkout
    cascade = EvaluatorCascade(tmp_path)
    candidate = _candidate(source_commit=commit)
    cascade.register_candidate(candidate)
    with sqlite3.connect(cascade.path) as con:
        raw = json.loads(con.execute("SELECT candidate_json FROM candidates").fetchone()[0])
        raw["candidate_id"] = "f" * 64
        con.execute("UPDATE candidates SET candidate_json=?", (json.dumps(raw),))
    with pytest.raises(RuntimeError, match="integrity"):
        validator(tmp_path, cascade, source).run_once()
    assert cascade.snapshot()["receipt_count"] == 0
