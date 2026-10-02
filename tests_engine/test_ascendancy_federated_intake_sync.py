from __future__ import annotations

import time

from icarus_engine.ascendancy.federated_intake import (
    FederatedResearchIntake,
    FederatedResearchIntakeSync,
)


def _snapshot(*, commit="a" * 40, packet="1" * 64, fresh=True):
    return {
        "schema_version": "icarus-brain-remote-sync-v1",
        "repository": "reppiks490/Icarus-engine",
        "ref": "main",
        "status": "green",
        "peer_packet_status": "green",
        "peer_packet_id": packet,
        "peer_source_commit": commit,
        "peer_source_commit_verified": True,
        "peer_source_commit_relation": "HEAD_OR_ANCESTOR",
        "peer_packet_fresh": fresh,
        "peer_packet_age_seconds": 30.0,
        "historical_context_status": "green",
        "historical_context_source_count": 1,
        "historical_candidate_evidence_count": 0,
        "historical_context_sources": [
            {
                "id": "robustness_guardian",
                "path": "automation_intelligence/agent_fabric/robustness_guardian/latest.json",
                "remote_blob_sha": "b" * 40,
                "run_id": "robustness-1",
                "run_status": "RUN_PERSISTED",
                "evidence_status": "HISTORICAL_RESEARCH_EVIDENCE",
                "collection_only": False,
                "research_context_eligible": True,
                "candidate_evidence_eligible": False,
                "foreign_evidence_only": True,
                "requires_foundry_and_evaluator": True,
                "summary": {
                    "RUN_CORE.findings": [
                        "Protected holdout identity should remain immutable."
                    ]
                },
                "subject": "Robustness Guardian",
                "execution_authorized": False,
                "production_decision_authorized": False,
            }
        ],
        "truth_contract": {
            "federation_schema": "icarus-engine-brain-federation-v1",
            "historical_context_mode": "RESEARCH_CONTEXT_ONLY",
            "historical_context_never_bypasses_foundry": True,
            "historical_context_never_bypasses_evaluator": True,
            "historical_context_never_grants_shadow_qualification": True,
            "historical_context_never_grants_execution_authority": True,
            "durability_receipts_are_substantive_evidence": False,
            "automatic_model_promotion": False,
            "automatic_execution_authority": False,
            "production_decision_authorized": False,
        },
        "execution_authorized": False,
        "production_decision_authorized": False,
    }


def test_sync_worker_projects_safe_remote_state_and_is_idempotent(tmp_path):
    current = _snapshot()
    intake = FederatedResearchIntake(tmp_path)
    sync = FederatedResearchIntakeSync(
        tmp_path,
        intake=intake,
        provider=lambda: current,
        interval_seconds=30,
    )

    one = sync.sync_once()
    assert one["status"] == "green"
    assert one["new_proposal_count"] == 1
    assert one["proposal_count"] == 1
    assert one["last_peer_packet_id"] == "1" * 64
    assert one["last_peer_source_commit"] == "a" * 40
    assert one["candidate_evidence_count"] == 0
    assert one["automatic_candidate_creation"] is False
    assert one["execution_authorized"] is False
    assert one["production_decision_authorized"] is False

    two = sync.sync_once()
    assert two["status"] == "green"
    assert two["new_proposal_count"] == 0
    assert intake.snapshot()["proposal_count"] == 1


def test_sync_worker_retains_last_good_state_when_peer_degrades(tmp_path):
    holder = {"value": _snapshot()}
    intake = FederatedResearchIntake(tmp_path)
    sync = FederatedResearchIntakeSync(
        tmp_path,
        intake=intake,
        provider=lambda: holder["value"],
    )
    good = sync.sync_once()
    assert good["status"] == "green"

    holder["value"] = _snapshot(fresh=False)
    degraded = sync.sync_once()
    assert degraded["status"] == "degraded"
    assert "fresh" in degraded["last_error"].lower()
    assert degraded["last_peer_packet_id"] == good["last_peer_packet_id"]
    assert degraded["last_peer_source_commit"] == good["last_peer_source_commit"]
    assert degraded["proposal_count"] == 1
    assert intake.snapshot()["proposal_count"] == 1
    assert degraded["execution_authorized"] is False


def test_sync_worker_advancing_peer_revision_adds_new_prompt_lineage(tmp_path):
    holder = {"value": _snapshot()}
    intake = FederatedResearchIntake(tmp_path)
    sync = FederatedResearchIntakeSync(
        tmp_path,
        intake=intake,
        provider=lambda: holder["value"],
    )
    sync.sync_once()

    newer = _snapshot(commit="f" * 40, packet="2" * 64)
    newer["historical_context_sources"][0]["remote_blob_sha"] = "e" * 40
    newer["historical_context_sources"][0]["summary"]["RUN_CORE.findings"] = [
        "A newer peer revision reports regime-label drift."
    ]
    holder["value"] = newer

    state = sync.sync_once()
    assert state["status"] == "green"
    assert state["last_peer_packet_id"] == "2" * 64
    assert state["last_peer_source_commit"] == "f" * 40
    assert state["new_proposal_count"] == 1
    assert state["proposal_count"] == 2
    assert set(intake.snapshot()["source_commits"]) == {"a" * 40, "f" * 40}


def test_sync_worker_background_lifecycle_is_idempotent(tmp_path):
    intake = FederatedResearchIntake(tmp_path)
    sync = FederatedResearchIntakeSync(
        tmp_path,
        intake=intake,
        provider=lambda: _snapshot(),
        interval_seconds=30,
    )

    sync.start()
    sync.start()
    deadline = time.time() + 2.0
    while time.time() < deadline and intake.snapshot()["proposal_count"] == 0:
        time.sleep(0.02)

    assert intake.snapshot()["proposal_count"] == 1
    assert sync.status()["running"] is True

    sync.close()
    sync.close()
    assert sync.status()["running"] is False
    assert sync.status()["execution_authorized"] is False


def test_sync_worker_never_invokes_provider_after_close(tmp_path):
    calls = {"n": 0}

    def provider():
        calls["n"] += 1
        return _snapshot()

    intake = FederatedResearchIntake(tmp_path)
    sync = FederatedResearchIntakeSync(
        tmp_path,
        intake=intake,
        provider=provider,
        interval_seconds=30,
    )
    sync.start()
    deadline = time.time() + 2.0
    while time.time() < deadline and calls["n"] == 0:
        time.sleep(0.02)
    sync.close()
    after = calls["n"]
    time.sleep(0.08)
    assert calls["n"] == after
