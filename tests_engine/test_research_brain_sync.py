from __future__ import annotations

import json

from icarus_engine.brain import brain_snapshot
from icarus_engine.research_brain_sync import BrainResearchSync


def _sha(char="a", n=64):
    return char * n


def _qualified_job(**changes):
    evidence = {
        "result_sha256": _sha("1"),
        "source_config_sha256": _sha("2"),
        "subbars_sha256": _sha("3"),
        "deep_sha256": _sha("4"),
    }
    selected = {"conf_min_votes": 5}
    result = {
        "status": "complete",
        "research_qualified": True,
        "accuracy_guaranteed": False,
        "study_hash": _sha("5"),
        "total_combinations": 2,
        "selected": selected,
        "manifest": {"dataset_hash": _sha("a"), "baseline_hash": _sha("b")},
        "trials": [{
            "inputs": selected,
            "result_evidence": {"train": evidence, "validation": evidence},
        }],
        "holdout_consumed": True,
        "holdout_evidence": evidence,
        "holdout_comparison": {"passed": True},
        "holdout": {
            "entries": 40,
            "win_rate": 0.55,
            "net_after_costs": 120.0,
            "expectancy_after_costs": 3.0,
            "max_drawdown_pct": 4.5,
        },
        "stress": {
            "status": "enabled",
            "holdout_evidence": evidence,
            "holdout_comparison": {"passed": True},
            "holdout": {
                "net_after_costs": 70.0,
                "expectancy_after_costs": 1.75,
                "max_drawdown_pct": 6.0,
            },
        },
        "qualification_reasons": [],
    }
    job = {
        "id": "a" * 16,
        "status": "complete",
        "asset": "NQ",
        "dataset_hash": _sha("a"),
        "baseline_hash": _sha("b"),
        "source_repo": "reppiks490/Icarus",
        "source_commit": "c" * 40,
        "source_revision_status": "exact_clean_git",
        "source_revision_eligible": True,
        "result": result,
        "error": None,
    }
    job.update(changes)
    return job


def _save(tmp_path, job):
    root = tmp_path / "research" / "studies"
    root.mkdir(parents=True)
    (root / f"{job['id']}.json").write_text(json.dumps(job, sort_keys=True), encoding="utf-8")


def test_qualified_research_becomes_partial_validated_candidate_not_shadow_qualified(tmp_path):
    _save(tmp_path, _qualified_job())
    sync = BrainResearchSync(tmp_path, interval_seconds=10)
    status = sync.sync_once()
    assert status["status"] == "green"
    assert status["candidates_recorded"] == 1

    snap = brain_snapshot(tmp_path, research_sync=status)
    candidate = snap["candidates"][0]
    assert candidate["stage"] == "validated"
    assert candidate["validation"]["provenance"] is True
    assert candidate["validation"]["oos"] is True
    assert candidate["validation"]["protected_holdout"] is True
    assert candidate["validation"]["costs_slippage_latency"] is None
    assert candidate["validation"]["independent_verification"] is None
    assert candidate["eligible_for_regime_swap"] is False
    assert snap["research_sync"]["status"] == "green"


def test_no_candidate_is_retained_as_negative_learning(tmp_path):
    job = _qualified_job(status="no_candidate")
    job["result"] = {
        "status": "no_candidate",
        "study_hash": _sha("5"),
        "manifest": {"dataset_hash": _sha("a"), "baseline_hash": _sha("b")},
        "trials": [],
        "selected": None,
        "qualification_reasons": [],
    }
    _save(tmp_path, job)
    sync = BrainResearchSync(tmp_path, interval_seconds=10)
    status = sync.sync_once()
    assert status["negative_results_recorded"] == 1
    snap = brain_snapshot(tmp_path)
    assert snap["candidates"] == []
    assert snap["events"][0]["kind"] == "learning"
    assert snap["events"][0]["status"] == "rejected"


def test_missing_exact_study_revision_blocks_candidate_admission(tmp_path):
    job = _qualified_job(source_commit=None, source_revision_status="unavailable", source_revision_eligible=False)
    _save(tmp_path, job)
    sync = BrainResearchSync(tmp_path, interval_seconds=10)
    status = sync.sync_once()
    assert status["blocked_revision_count"] == 1
    snap = brain_snapshot(tmp_path)
    assert snap["candidates"] == []
    assert snap["events"][0]["status"] == "blocked"


def test_research_sync_is_idempotent(tmp_path):
    _save(tmp_path, _qualified_job())
    sync = BrainResearchSync(tmp_path, interval_seconds=10)
    first = sync.sync_once()
    second = sync.sync_once()
    assert first["candidates_recorded"] == 1
    assert second["candidates_recorded"] == 1
    assert len(brain_snapshot(tmp_path)["candidates"]) == 1
