"""Constellation swarm acceptance: full fanout, bounded evidence and tribunal."""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from icarus_engine.omnigenesis.constellation import (
    arbitrate, build_plan, main, run_worker,
)
from icarus_engine.omnigenesis.contracts import identity


def full(seed=49021):
    plan = build_plan(seed)
    receipts = [run_worker(plan, j["lane"], j["shard"]) for j in plan["jobs"]]
    return plan, receipts


def test_six_unique_specialist_lanes_twelve_sharded_workers_and_replay_tribunal():
    plan, records = full()
    assert plan["worker_count"] == 12
    assert len({j["lane"] for j in plan["jobs"]}) == 6
    assert {j["shard"] for j in plan["jobs"]} == {0, 1}
    assert plan["authority"] == {
        "research_only": True, "execution_authorized": False,
        "production_decision_authorized": False, "auto_promote": False}
    assert plan["broker_calls_allowed"] is False
    assert plan["automatic_promotion"] is False
    assert plan["max_retries_per_worker"] == 0
    assert plan["plan_id"] == identity({k: v for k, v in plan.items()
                                        if k != "plan_id"})
    kinds = {r["summary"]["evidence_kind"] for r in records}
    assert len(kinds) == 6
    assert {r["lane"] for r in records} == {
        "chronos", "execution", "reconciliation", "nemesis",
        "worldline", "memory"}
    assert all(r["status"] == "PASS_RESEARCH_ONLY" for r in records)
    assert all(r["broker_order_count"] == 0 for r in records)
    assert all(r["production_qualified"] is False for r in records)
    assert all(r["receipt_id"] == identity(
        {k: v for k, v in r.items() if k != "receipt_id"}) for r in records)
    review = arbitrate(plan, records)
    assert review == arbitrate(plan, list(reversed(records)))
    assert review["passed_workers"] == 12
    assert review["expected_workers"] == 12
    assert review["broker_order_count"] == 0
    assert review["strategy_promoted"] is False
    assert review["release_authorized"] is False
    assert review["independent_scientific_validation"] is False
    assert review["status"] == "RESEARCH_CONSISTENCY_PASS_PENDING_INDEPENDENT_REVIEW"
    assert review["tribunal_id"] == identity({k: v for k, v in review.items()
                                             if k != "tribunal_id"})


def test_different_seed_changes_evidence_but_not_permissions():
    a = full(101)
    b = full(102)
    assert a[0]["plan_id"] != b[0]["plan_id"]
    assert a[1][0]["receipt_id"] != b[1][0]["receipt_id"]
    assert a[1][0]["authority"] == b[1][0]["authority"]


@pytest.mark.parametrize("field,value,match", [
    ("seed", True, "seed"),
    ("seed", -1, "seed"),
    ("seed", 1 << 32, "seed"),
])
def test_seed_input_bounded_without_boolean_coercion(field, value, match):
    with pytest.raises(ValueError, match=match):
        build_plan(value)


def test_plan_mutation_cannot_add_workers_or_authority():
    plan = build_plan(23)
    forged = copy.deepcopy(plan)
    forged["broker_calls_allowed"] = True
    with pytest.raises(ValueError, match="plan mismatch"):
        run_worker(forged, "chronos", 0)
    forged = copy.deepcopy(plan)
    forged["jobs"].append({"lane": "live_broker", "shard": 2})
    with pytest.raises(ValueError, match="plan mismatch"):
        run_worker(forged, "chronos", 0)
    forged = copy.deepcopy(plan)
    forged["authority"]["auto_promote"] = True
    with pytest.raises(ValueError, match="plan mismatch"):
        run_worker(forged, "chronos", 0)


@pytest.mark.parametrize("lane,shard,match", [
    ("broker", 0, "unapproved"),
    ("chronos", 4, "shard"),
    ("chronos", True, "shard"),
])
def test_unregistered_worker_cannot_run(lane, shard, match):
    with pytest.raises(ValueError, match=match):
        run_worker(build_plan(5), lane, shard)


def test_missing_duplicate_and_extra_worker_receipts_are_fatal():
    plan, receipts = full(12)
    with pytest.raises(ValueError, match="missing, extra"):
        arbitrate(plan, receipts[:-1])
    duplicate = receipts[:-1] + [copy.deepcopy(receipts[0])]
    with pytest.raises(ValueError, match="duplicate"):
        arbitrate(plan, duplicate)
    forged = copy.deepcopy(receipts)
    forged[0]["lane"] = "live"
    with pytest.raises(ValueError, match="unexpected"):
        arbitrate(plan, forged)


def test_payload_cannot_claim_real_profit_or_promote_its_own_research():
    plan, receipts = full(13)
    forged = copy.deepcopy(receipts)
    forged[0]["broker_order_count"] = 1
    forged[0]["receipt_id"] = identity({k: v for k, v in forged[0].items()
                                        if k != "receipt_id"})
    with pytest.raises(ValueError, match="authority/provenance"):
        arbitrate(plan, forged)
    forged = copy.deepcopy(receipts)
    forged[0]["summary"]["profitability_verified"] = True
    forged[0]["receipt_id"] = identity({k: v for k, v in forged[0].items()
                                        if k != "receipt_id"})
    with pytest.raises(ValueError, match="computation mismatch"):
        arbitrate(plan, forged)


def test_worker_receipt_sha256_integrity_rejects_tampered_results():
    plan, receipts = full(14)
    forged = copy.deepcopy(receipts)
    forged[0]["summary"]["extra_causality_delay_bars"] = -9
    with pytest.raises(ValueError, match="receipt hash"):
        arbitrate(plan, forged)


def test_specialist_truth_boundaries():
    plan, reports = full(1011)
    by_lane = {}
    for r in reports:
        by_lane.setdefault(r["lane"], []).append(r["summary"])
    assert all(x["extra_causality_delay_bars"] > 0
               and x["hypothetical_fills_only"] for x in by_lane["chronos"])
    assert all(x["profitability_verified"] is False
               and x["synthetic_drawdown_cents"] >= 0
               for x in by_lane["execution"])
    assert all(x["reconciliation_consistent_with_mock_input"]
               for x in by_lane["reconciliation"])
    assert all(x["rejected_count"] == 3 and
               x["false_acceptance_count"] == 0 for x in by_lane["nemesis"])
    assert all(x["engine_replay_verified"] is False and
               x["source_authenticity_verified"] is False
               for x in by_lane["worldline"])
    assert all(x["idempotent_derived_replay"] is True and
               x["execution_authorized"] is False
               for x in by_lane["memory"])


def test_plan_worker_tribunal_cli_files_reject_missing_or_extra_artifacts(tmp_path):
    plan_path = tmp_path / "plan.json"
    main(["plan", "--seed", "77", "--output", str(plan_path)])
    plan = json.loads(plan_path.read_text())
    folder = tmp_path / "worker-artifacts"
    folder.mkdir()
    for j in plan["jobs"]:
        name = folder / f"worker-{j['lane']}-{j['shard']}.json"
        main(["worker", "--plan", str(plan_path),
              "--lane", j["lane"], "--shard", str(j["shard"]),
              "--output", str(name)])
    outcome = tmp_path / "tribunal.json"
    main(["tribunal", "--plan", str(plan_path),
          "--worker-dir", str(folder), "--output", str(outcome)])
    report = json.loads(outcome.read_text())
    assert report["passed_workers"] == 12
    with pytest.raises(FileExistsError):
        main(["tribunal", "--plan", str(plan_path),
              "--worker-dir", str(folder), "--output", str(outcome)])
    extra = folder / "rogue.json"
    extra.write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="artifact count mismatch"):
        main(["tribunal", "--plan", str(plan_path),
              "--worker-dir", str(folder), "--output", str(tmp_path / "bad.json")])


def test_plan_file_input_rejects_symlink_and_malformed_bytes(tmp_path):
    p = tmp_path / "plan.json"
    p.write_text("not-json", encoding="utf-8")
    with pytest.raises(ValueError, match="malformed"):
        main(["worker", "--plan", str(p), "--lane", "chronos",
              "--shard", "0", "--output", str(tmp_path / "out.json")])
    p.write_text(json.dumps(build_plan(3)), encoding="utf-8")
    symlink = tmp_path / "link.json"
    symlink.symlink_to(p)
    with pytest.raises(ValueError, match="symlink"):
        main(["worker", "--plan", str(symlink), "--lane", "chronos",
              "--shard", "0", "--output", str(tmp_path / "out.json")])


def test_duplicate_json_keys_fail_before_work_is_scheduled(tmp_path):
    payload = tmp_path / "duplicated.json"
    payload.write_text('{"seed":1,"seed":2}', encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate constellation JSON key"):
        main(["worker", "--plan", str(payload), "--lane", "chronos",
              "--shard", "0", "--output", str(tmp_path / "out.json")])


def test_evidence_filename_must_match_typed_lane_and_shard(tmp_path):
    plan = build_plan(71)
    p = tmp_path / "plan.json"
    p.write_text(json.dumps(plan), encoding="utf-8")
    folder = tmp_path / "worker-evidence"
    folder.mkdir()
    for item in plan["jobs"]:
        a = run_worker(plan, item["lane"], item["shard"])
        name = folder / f"worker-{item['lane']}-{item['shard']}.json"
        name.write_text(json.dumps(a), encoding="utf-8")
    before = folder / "worker-chronos-0.json"
    after = folder / "worker-rogue-0.json"
    before.rename(after)
    with pytest.raises(ValueError, match="filename/identity mismatch"):
        main(["tribunal", "--plan", str(p), "--worker-dir", str(folder),
              "--output", str(tmp_path / "report.json")])


def test_symlinked_artifact_directory_is_not_trusted(tmp_path):
    p = tmp_path / "plan.json"
    p.write_text(json.dumps(build_plan(19)), encoding="utf-8")
    target = tmp_path / "actual-dir"
    target.mkdir()
    link = tmp_path / "artifact-link"
    link.symlink_to(target, target_is_directory=True)
    with pytest.raises(ValueError, match="worker directory missing"):
        main(["tribunal", "--plan", str(p), "--worker-dir", str(link),
              "--output", str(tmp_path / "report.json")])
