"""Phase 25 actual-worker-status observability, not a fabricated live swarm."""
from __future__ import annotations

from copy import deepcopy
import json
import subprocess
import sys

import pytest

from icarus_engine.omnigenesis.constellation import build_plan, run_worker, arbitrate
from icarus_engine.omnigenesis.constellation_recovery import checkpoint_recovery
from icarus_engine.omnigenesis.constellation_observation import (
    observe_constellation, main,
)
from icarus_engine.omnigenesis.contracts import identity
from icarus_engine.omnigenesis.ledger import ResearchLedger


_RUN_ID = "45121812267"
_SHA = "b" * 40


@pytest.fixture(scope="module")
def examples():
    plan = build_plan(49021)
    receipts = [run_worker(plan, j["lane"], j["shard"]) for j in plan["jobs"]]
    checkpoint = checkpoint_recovery(plan, receipts, run_id=_RUN_ID,
                                     attempt=1, source_sha=_SHA)
    tribunal = arbitrate(plan, receipts)
    return plan, receipts, checkpoint, tribunal


def test_completed_tribunal_produces_immutable_read_only_twelve_worker_snapshot(examples):
    plan, receipts, checkpoint, tribunal = examples
    record = observe_constellation(plan, checkpoint, tribunal)
    assert record == observe_constellation(plan, checkpoint, tribunal)
    assert record["observation_id"] == identity(
        {k: v for k, v in record.items() if k != "observation_id"})
    assert record["worker_count"] == record["completed_count"] == 12
    assert len(record["workers"]) == 12
    assert all(x["status"] == "COMPLETED_RESEARCH_ONLY" for x in record["workers"])
    assert {x["lane"] for x in record["workers"]} == {
        "chronos", "execution", "reconciliation", "nemesis", "worldline", "memory"}
    assert record["authority"]["execution_authorized"] is False
    assert record["github_api_provenance_verified"] is False
    assert record["source_commit_attested"] is False
    assert record["snapshot_is_live"] is False
    assert record["active_workers_now"] == 0
    assert record["real_profitability_verified"] is False
    assert record["release_authorized"] is False
    assert record["broker_order_count"] == 0
    assert record["strategy_promoted"] is False


def test_missing_checkpoint_evidence_refused_even_if_tribunal_claims_pass(examples):
    plan, receipts, cp, tribunal = examples
    partial = checkpoint_recovery(plan, receipts[:-1], run_id=_RUN_ID,
                                  attempt=1, source_sha=_SHA)
    with pytest.raises(ValueError, match="incomplete or failed"):
        observe_constellation(plan, partial, tribunal)


def test_fake_tribunal_claims_cannot_enter_observatory(examples):
    plan, receipts, cp, tribunal = examples
    changed = deepcopy(tribunal)
    changed["release_authorized"] = True
    changed["tribunal_id"] = identity(
        {k: v for k, v in changed.items() if k != "tribunal_id"})
    with pytest.raises(ValueError, match="does not match"):
        observe_constellation(plan, cp, changed)
    changed = deepcopy(tribunal)
    changed["passed_workers"] = 0
    with pytest.raises(ValueError, match="does not match"):
        observe_constellation(plan, cp, changed)


def test_recovered_results_require_full_previous_checkpoint_lineage(examples):
    plan, receipts, cp, tribunal = examples
    first = checkpoint_recovery(plan, receipts[:-1], run_id=_RUN_ID,
                                attempt=1, source_sha=_SHA)
    second = checkpoint_recovery(plan, receipts, run_id=_RUN_ID, attempt=1,
                                 source_sha=_SHA, previous=first)
    with pytest.raises(ValueError, match="requires original predecessor"):
        observe_constellation(plan, second, tribunal)
    result = observe_constellation(plan, second, tribunal, predecessor=first)
    assert result["retry_round"] == 1
    assert result["predecessor_checkpoint_id"] == first["checkpoint_id"]
    assert result["completed_count"] == 12
    wrong = deepcopy(first)
    wrong["context"]["source_sha"] = "c" * 40
    wrong["checkpoint_id"] = identity(
        {k: v for k, v in wrong.items() if k != "checkpoint_id"})
    with pytest.raises(ValueError, match="predecessor mismatch"):
        observe_constellation(plan, second, tribunal, predecessor=wrong)


def test_first_pass_snapshot_rejects_unexpected_predecessor(examples):
    plan, receipts, cp, tribunal = examples
    with pytest.raises(ValueError, match="unexpected previous"):
        observe_constellation(plan, cp, tribunal, predecessor=cp)


def test_observation_is_safe_to_store_only_as_derived_ledger_artifact(examples, tmp_path):
    plan, receipts, cp, tribunal = examples
    ledger = ResearchLedger(tmp_path)
    digest = ledger.append_constellation(plan, cp, tribunal)
    assert digest == ledger.append_constellation(plan, cp, tribunal)
    snap = ledger.snapshot()
    assert snap["artifact_count"] == 1
    assert snap["study_count"] == 0
    row = snap["recent_artifacts"][0]
    assert row["artifact_id"] == digest
    assert row["kind"] == "constellation_observation"
    assert row["source_id"] == observe_constellation(
        plan, cp, tribunal)["observation_id"]
    assert row["status"] == "LOCAL_REPLAY_ONLY"
    assert row["title"] == "Completed Constellation research receipt audit"
    assert row["metric"] == 12
    assert row["research_only"] is True
    serialized = json.dumps(snap, sort_keys=True)
    assert "accepted_receipts" not in serialized
    assert "claimed_github_run" not in serialized
    assert "broker_credentials" not in serialized


def test_ledger_fail_closed_on_forged_or_partial_evidence(examples, tmp_path):
    plan, receipts, cp, tribunal = examples
    store = ResearchLedger(tmp_path)
    forged = deepcopy(cp)
    forged["accepted_receipts"][0]["broker_order_count"] = 1
    forged["checkpoint_id"] = identity(
        {k: v for k, v in forged.items() if k != "checkpoint_id"})
    with pytest.raises(ValueError, match="tampered or incompatible"):
        store.append_constellation(plan, forged, tribunal)
    missing = checkpoint_recovery(plan, receipts[:-1], run_id=_RUN_ID,
                                  attempt=1, source_sha=_SHA)
    with pytest.raises(ValueError, match="incomplete or failed"):
        store.append_constellation(plan, missing, tribunal)
    assert store.snapshot()["artifact_count"] == 0


def test_strict_observation_cli_writes_once_without_connecting_to_brokers(
        examples, tmp_path, capsys):
    plan, receipts, cp, tribunal = examples
    paths = [tmp_path / x for x in ("plan.json", "checkpoint.json", "tribunal.json")]
    for path, data in zip(paths, (plan, cp, tribunal)):
        path.write_text(json.dumps(data), encoding="utf-8")
    target = tmp_path / "observation.json"
    args = ["--plan", str(paths[0]), "--checkpoint", str(paths[1]),
            "--tribunal", str(paths[2]), "--output", str(target)]
    main(args)
    report = json.loads(target.read_text())
    assert report["active_workers_now"] == 0
    assert report["broker_order_count"] == 0
    assert report["observation_id"] == observe_constellation(
        plan, cp, tribunal)["observation_id"]
    with pytest.raises(FileExistsError):
        main(args)


def test_main_cli_import_refuses_forged_live_claim_and_exposes_ledger_snapshot(
        examples, tmp_path):
    plan, receipts, cp, tribunal = examples
    paths = [tmp_path / x for x in ("plan.json", "checkpoint.json", "tribunal.json")]
    for path, data in zip(paths, (plan, cp, tribunal)):
        path.write_text(json.dumps(data), encoding="utf-8")
    cmd = [sys.executable, "-m", "icarus_engine.omnigenesis",
           "constellation-import",
           "--plan", str(paths[0]),
           "--checkpoint", str(paths[1]),
           "--tribunal", str(paths[2]),
           "--root", str(tmp_path)]
    run = subprocess.run(cmd, text=True, capture_output=True, check=True)
    status = json.loads(run.stdout)
    assert status["status"] == "LOCAL_REPLAY_ONLY"
    assert status["broker_order_count"] == 0
    assert status["github_api_provenance_verified"] is False
    assert ResearchLedger(tmp_path).snapshot()["recent_artifacts"][0]["metric"] == 12
