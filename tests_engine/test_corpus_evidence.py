"""Native metadata receipts are the positive oracle; injected faults are negative controls."""
import copy
import hashlib
import importlib
import json
from pathlib import Path

import pytest

BUNDLE = Path(__file__).parents[1] / "icarus_engine" / "corpus-consumption.json"
NOW = 1792401987000000000


def _api():
    return importlib.import_module("icarus_engine.corpus_evidence")


def _bundle():
    return json.loads(BUNDLE.read_bytes())


def _write(tmp_path, bundle):
    path = tmp_path / "evidence.json"
    path.write_text(json.dumps(bundle))
    return path


def _fault(tmp_path, monkeypatch, change, cache=0):
    bundle = _bundle()
    artifact = bundle["artifacts"][cache]
    receipt = json.loads(artifact["receipt_json"])
    change(receipt)
    artifact["receipt_json"] = json.dumps(receipt)
    artifact["receipt_sha256"] = hashlib.sha256(artifact["receipt_json"].encode()).hexdigest()
    # Exercise semantic validation independently of the fixed hash trust anchor.
    monkeypatch.setitem(_api()._PINNED, artifact["cache_name"],
                        (artifact["artifact_id"], artifact["receipt_sha256"]))
    return _api().snapshot(now_ns=NOW, path=_write(tmp_path, bundle))


def _unavailable(result):
    assert result["status"] == "UNAVAILABLE"
    assert result["reason"] == "INVALID_CORPUS_EVIDENCE"
    assert result["corpora"] == []
    assert result["live_feed_qualified"] is result["strategy_qualified"] is result["execution_authorized"] is False


def test_actual_three_artifacts_are_projected_with_historical_coverage_and_four_workspaces():
    result = _api().snapshot(now_ns=NOW)
    assert result["status"] == "HISTORICAL_CONSUMPTION_VERIFIED"
    assert result["run_id"] == 39115319263
    assert [c["artifact_id"] for c in result["corpora"]] == [12132181638, 12132122538, 12132291117]
    assert [c["dataset_count"] for c in result["corpora"]] == [32, 2, 1]
    assert result["corpora"][0]["source_rows"] == 4_633_264
    assert [c["retained_rows"] for c in result["corpora"]] == [192_000, 12_000, 6000]
    assert [c["paper_warmup_used"] for c in result["corpora"]] == [True, False, True]
    for corpus, counts in zip(result["corpora"], (12, 0, 1)):
        assert [w["id"] for w in corpus["workspaces"]] == ["cc1", "cc2", "cc3", "cc4"]
        assert [w["warm_asset_count"] for w in corpus["workspaces"]] == [counts] * 4
        assert corpus["historical"] is True
        assert corpus["age_seconds"] == NOW // 10**9 - corpus["latest_bar_closed_ts"]
    third = result["corpora"][2]
    assert third["age_seconds"] > 365 * 86400
    assert result["live_feed_qualified"] is result["strategy_qualified"] is result["execution_authorized"] is False
    public = json.dumps(result)
    assert "receipt_json" not in public and "inputs" not in public and "pnl" not in public.lower()


@pytest.mark.parametrize("field,value", [("run_id", 1), ("source_commit", "f" * 40),
    ("consumer_commit", "f" * 40), ("source_repo", "other/repo"), ("private_path", "/private/SECRET")])
def test_bundle_identity_and_privacy_fields_fail_closed(tmp_path, field, value):
    bundle = _bundle()
    bundle[field] = value
    result = _api().snapshot(now_ns=NOW, path=_write(tmp_path, bundle))
    _unavailable(result)
    assert "SECRET" not in json.dumps(result)


@pytest.mark.parametrize("fault", ["bytes", "sha", "artifact", "duplicate_cache"])
def test_artifact_tampering_or_swapping_is_rejected(tmp_path, fault):
    bundle = _bundle()
    first = bundle["artifacts"][0]
    if fault == "bytes": first["receipt_json"] += " "
    elif fault == "sha": first["receipt_sha256"] = "0" * 64
    elif fault == "artifact": first["artifact_id"] = 123
    else: bundle["artifacts"][1] = copy.deepcopy(first)
    _unavailable(_api().snapshot(now_ns=NOW, path=_write(tmp_path, bundle)))


@pytest.mark.parametrize("fault", ["authority", "privacy", "schema", "dataset_identity", "read_identity",
    "no_positive_read", "duplicate_workspace", "false_warmup", "context_warmup", "future_bar"])
def test_semantic_receipt_faults_fail_closed_even_with_matching_byte_hash(tmp_path, monkeypatch, fault):
    def change(receipt):
        if fault == "authority": receipt["execution_authorized"] = True
        elif fault == "privacy": receipt["datasets"][0]["api_key"] = "SECRET_MARKER"
        elif fault == "schema": receipt["schema_version"] = "unknown"
        elif fault == "dataset_identity": receipt["datasets"][0]["source_sha256"] = "0" * 64
        elif fault == "read_identity": receipt["read_receipts"][0]["source_sha256"] = "0" * 64
        elif fault == "no_positive_read":
            target = receipt["datasets"][0]["dataset_id"]
            receipt["read_receipts"] = [r for r in receipt["read_receipts"] if r["dataset_id"] != target]
        elif fault == "duplicate_workspace": receipt["workspaces"][1] = copy.deepcopy(receipt["workspaces"][0])
        elif fault == "false_warmup": receipt["paper_warmup_used"] = False
        elif fault == "context_warmup": receipt["paper_warmup_used"] = True
        elif fault == "future_bar": receipt["datasets"][0]["last_ts"] = NOW // 10**9 + 300
    result = _fault(tmp_path, monkeypatch, change, 1 if fault == "context_warmup" else 0)
    _unavailable(result)
    assert "SECRET_MARKER" not in json.dumps(result)


@pytest.mark.parametrize("kind", ["missing", "malformed", "oversized", "nested", "duplicate_keys"])
def test_invalid_files_are_bounded_and_never_escape_errors(tmp_path, kind):
    path = tmp_path / "bad.json"
    if kind == "malformed": path.write_bytes(b"{not-json")
    elif kind == "oversized": path.write_bytes(b" " * (2 * 1024 * 1024 + 1))
    elif kind == "nested": path.write_text("[" * 10000 + "0" + "]" * 10000)
    elif kind == "duplicate_keys": path.write_text('{"schema_version":"a","schema_version":"b"}')
    _unavailable(_api().snapshot(now_ns=NOW, path=path))


@pytest.mark.parametrize("clock", [True, -1, 1, "today"])
def test_invalid_or_precapture_current_clock_is_unavailable(clock):
    _unavailable(_api().snapshot(now_ns=clock))


def test_later_clock_increases_source_age_without_promoting_qualification():
    initial = _api().snapshot(now_ns=NOW)
    later = _api().snapshot(now_ns=NOW + 86400 * 10**9)
    assert later["corpora"][0]["age_seconds"] == initial["corpora"][0]["age_seconds"] + 86400
    assert later["live_feed_qualified"] is False
