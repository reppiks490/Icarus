"""Adversarial Phase 24 Constellation recovery, resume and incident tests."""
from __future__ import annotations

from copy import deepcopy
import json

import pytest

from icarus_engine.omnigenesis.constellation import build_plan, run_worker
from icarus_engine.omnigenesis.constellation_recovery import (
    checkpoint_recovery, verify_checkpoint, context, main,
)
from icarus_engine.omnigenesis.contracts import identity


@pytest.fixture(scope="module")
def evidence():
    plan = build_plan(137)
    receipts = [run_worker(plan, j["lane"], j["shard"]) for j in plan["jobs"]]
    return plan, receipts


def checkpoint(plan, receipts, *, previous=None, run_id="45121812267",
               attempt=1, source_sha="a" * 40):
    return checkpoint_recovery(plan, receipts, run_id=run_id,
                               attempt=attempt, source_sha=source_sha,
                               previous=previous)


def test_complete_evidence_checkpoint_never_authorizes_trading(evidence):
    plan, receipts = evidence
    x = checkpoint(plan, receipts)
    assert x == checkpoint(plan, list(reversed(receipts)))
    assert verify_checkpoint(plan, x) == x
    assert x["checkpoint_id"] == identity(
        {k: v for k, v in x.items() if k != "checkpoint_id"})
    assert x["status"] == "COMPLETE_PENDING_TRIBUNAL"
    assert x["accepted_count"] == 12
    assert x["pending_count"] == 0
    assert x["retry_round"] == 0
    assert x["retry_jobs"] == []
    assert x["broker_order_count"] == 0
    assert x["same_source_recomputation"] is True
    assert x["independent_review_required"] is True


def test_one_missing_worker_triggers_only_exact_missing_shard(evidence):
    plan, receipts = evidence
    x = checkpoint(plan, receipts[:-1])
    assert verify_checkpoint(plan, x) == x
    assert x["status"] == "RETRY_REQUIRED"
    assert x["accepted_count"] == 11
    assert x["pending_count"] == 1
    assert x["retry_jobs"] == [plan["jobs"][-1]]
    assert x["pending_jobs"] == [plan["jobs"][-1]]
    assert x["retry_round"] == 0


def test_recovery_becomes_complete_with_second_attempt_and_chain(evidence):
    plan, receipts = evidence
    first = checkpoint(plan, receipts[:-1])
    resumed = checkpoint(plan, receipts, previous=first)
    assert verify_checkpoint(plan, resumed) == resumed
    assert resumed["retry_round"] == 1
    assert resumed["previous_checkpoint_id"] == first["checkpoint_id"]
    assert resumed["status"] == "COMPLETE_PENDING_TRIBUNAL"
    assert resumed["accepted_count"] == 12
    assert resumed["pending_count"] == 0
    assert resumed["retry_jobs"] == []


def test_second_round_cannot_infinite_retry_or_self_certify(evidence):
    plan, receipts = evidence
    first = checkpoint(plan, receipts[:-2])
    second = checkpoint(plan, receipts[:-1], previous=first)
    assert second["retry_round"] == 1
    assert second["status"] == "FAIL_CLOSED_RETRY_EXHAUSTED"
    assert second["pending_count"] == 1
    assert second["retry_jobs"] == []
    assert second["independent_review_required"] is True
    with pytest.raises(ValueError, match="no eligible unfinished"):
        checkpoint(plan, receipts, previous=second)


def test_no_prior_worker_receipts_fails_closed_not_12_uncapped_retries(evidence):
    plan, _ = evidence
    report = checkpoint(plan, [])
    assert report["status"] == "FAIL_CLOSED_NO_EVIDENCE"
    assert report["pending_count"] == 12
    assert report["retry_jobs"] == []
    assert report["broker_order_count"] == 0


def test_duplicate_unregistered_and_mutated_partial_receipts_refused(evidence):
    plan, receipts = evidence
    with pytest.raises(ValueError, match="duplicate"):
        checkpoint(plan, [receipts[0], receipts[0]])
    forged = deepcopy(receipts[0])
    forged["summary"]["evidence_kind"] = "REAL_EXCHANGE_ORDER"
    forged["receipt_id"] = identity(
        {k: v for k, v in forged.items() if k != "receipt_id"})
    with pytest.raises(ValueError, match="tampered"):
        checkpoint(plan, [forged])
    forged = deepcopy(receipts[0])
    forged["lane"] = "live_broker"
    with pytest.raises(ValueError, match="unregistered"):
        checkpoint(plan, [forged])


def test_monotonic_continuation_cannot_drop_existing_successes(evidence):
    plan, receipts = evidence
    first = checkpoint(plan, receipts[:-2])
    with pytest.raises(ValueError, match="removed or changed"):
        checkpoint(plan, receipts[-2:], previous=first)


def test_context_source_commit_and_run_id_are_bound_to_checkpoint(evidence):
    plan, receipts = evidence
    first = checkpoint(plan, receipts[:-1])
    for altered in (
        {"run_id": "45121812268"},
        {"source_sha": "b" * 40},
        {"attempt": 2},
    ):
        with pytest.raises(ValueError, match="source/run mismatch"):
            checkpoint(plan, receipts, previous=first, **altered)


def test_forged_checkpoint_status_retry_quota_digest_rejected(evidence):
    plan, receipts = evidence
    first = checkpoint(plan, receipts[:-1])
    for key, value in (
        ("status", "APPROVED_FOR_LIVE_TRADING"),
        ("retry_round", 1),
        ("broker_order_count", 1),
        ("accepted_count", 12),
        ("checkpoint_id", "0" * 64),
        ("retry_jobs", []),
    ):
        altered = deepcopy(first)
        altered[key] = value
        with pytest.raises(ValueError, match="checkpoint|initial checkpoint"):
            verify_checkpoint(plan, altered)


def test_unexpected_json_or_context_values_refused(evidence):
    plan, receipts = evidence
    p = checkpoint(plan, receipts[:-1])
    p["credentials"] = "injected"
    with pytest.raises(ValueError, match="schema"):
        verify_checkpoint(plan, p)
    with pytest.raises(ValueError, match="source revision"):
        context("123", 1, "nothex")
    with pytest.raises(ValueError, match="run attempt"):
        context("123", True, "a" * 40)
    with pytest.raises(ValueError, match="run id"):
        context("0", 1, "a" * 40)


def test_completed_checkpoint_cannot_be_reopened_for_retries(evidence):
    plan, receipts = evidence
    complete = checkpoint(plan, receipts)
    with pytest.raises(ValueError, match="no eligible unfinished"):
        checkpoint(plan, receipts, previous=complete)


def test_cli_records_bounded_recovery_then_resumption(evidence, tmp_path):
    plan, receipts = evidence
    plan_file = tmp_path / "plan.json"
    plan_file.write_text(json.dumps(plan), encoding="utf-8")
    evidence_dir = tmp_path / "workers"
    evidence_dir.mkdir()
    for rec in receipts[:-1]:
        name = evidence_dir / f"worker-{rec['lane']}-{rec['shard']}.json"
        name.write_text(json.dumps(rec), encoding="utf-8")
    one = tmp_path / "recovery-0.json"
    base = ["--plan", str(plan_file), "--worker-dir", str(evidence_dir),
            "--source-sha", "a" * 40, "--run-id", "45121812267",
            "--run-attempt", "1"]
    main(base + ["--output", str(one)])
    saved = json.loads(one.read_text())
    assert saved["status"] == "RETRY_REQUIRED"
    with pytest.raises(FileExistsError):
        main(base + ["--output", str(one)])
    missing = receipts[-1]
    (evidence_dir / f"worker-{missing['lane']}-{missing['shard']}.json").write_text(
        json.dumps(missing), encoding="utf-8")
    two = tmp_path / "recovery-1.json"
    main(base + ["--previous", str(one), "--output", str(two)])
    final = json.loads(two.read_text())
    assert final["status"] == "COMPLETE_PENDING_TRIBUNAL"
    assert final["previous_checkpoint_id"] == saved["checkpoint_id"]


def test_cli_rejects_conflicting_duplicate_keys_and_symlinked_inputs(
        evidence, tmp_path):
    plan, receipts = evidence
    bad = tmp_path / "plan.json"
    bad.write_text('{"seed":5,"seed":6}', encoding="utf-8")
    worker_dir = tmp_path / "workers"
    worker_dir.mkdir()
    args = ["--plan", str(bad), "--worker-dir", str(worker_dir),
            "--source-sha", "a" * 40, "--run-id", "45121812267",
            "--run-attempt", "1", "--output", str(tmp_path / "output.json")]
    with pytest.raises(ValueError, match="duplicate recovery JSON key"):
        main(args)
    bad.write_text(json.dumps(plan), encoding="utf-8")
    symlink = tmp_path / "worker-link"
    symlink.symlink_to(worker_dir, target_is_directory=True)
    args[args.index(str(worker_dir))] = str(symlink)
    with pytest.raises(ValueError, match="symlinked"):
        main(args)


def test_cli_rejects_forged_artifact_filename(evidence, tmp_path):
    plan, receipts = evidence
    p = tmp_path / "plan.json"
    p.write_text(json.dumps(plan), encoding="utf-8")
    folder = tmp_path / "workers"
    folder.mkdir()
    (folder / "worker-rogue-0.json").write_text(
        json.dumps(receipts[0]), encoding="utf-8")
    with pytest.raises(ValueError, match="file identity"):
        main(["--plan", str(p), "--worker-dir", str(folder),
              "--source-sha", "a" * 40, "--run-id", "45121812267",
              "--run-attempt", "1", "--output", str(tmp_path / "output.json")])


def test_nested_recovery_jobs_cannot_skip_because_original_worker_failed():
    """GitHub implicitly tests success() unless a failure-aware condition exists."""
    from pathlib import Path
    workflow = (
        Path(__file__).resolve().parents[1]
        / ".github/workflows/omnigenesis-constellation.yml"
    ).read_text(encoding="utf-8")
    assert "  recovery-plan:" in workflow
    assert "if: ${{ always() && needs.seal-plan.result == 'success' }}" in workflow
    assert "  retry-workers:" in workflow
    assert ("if: ${{ always() && needs.recovery-plan.result == 'success' "
            "&& needs.recovery-plan.outputs.retry_needed == 'true' }}" in workflow)
    assert "  recovery-finalize:" in workflow
    assert "needs: [seal-plan, recovery-plan, retry-workers]" in workflow
    assert "  evidence-tribunal:" in workflow
    assert ("if: ${{ always() && needs.recovery-finalize.result == 'success' }}"
            in workflow)
    assert "needs: [seal-plan, recovery-finalize]" in workflow
    assert "max-parallel: 6" in workflow
    assert "contents: read" in workflow
    assert "contents: write" not in workflow
