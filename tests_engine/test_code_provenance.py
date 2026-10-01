from __future__ import annotations

from icarus_engine.code_provenance import local_code_provenance


def test_explicit_git_sha_is_exact_candidate_provenance(monkeypatch):
    monkeypatch.setenv("ICARUS_GIT_SHA", "a" * 40)
    out = local_code_provenance("/definitely/not/used")
    assert out["repository"] == "reppiks490/Icarus"
    assert out["commit"] == "a" * 40
    assert out["candidate_revision_eligible"] is True


def test_invalid_explicit_git_sha_does_not_mint_provenance(monkeypatch, tmp_path):
    monkeypatch.setenv("ICARUS_GIT_SHA", "not-a-sha")
    out = local_code_provenance(tmp_path)
    assert out["candidate_revision_eligible"] is False
    assert out["commit"] is None
