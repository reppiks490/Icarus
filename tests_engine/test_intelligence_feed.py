import json
from pathlib import Path
import shutil
import subprocess

import pytest

from icarus_engine.learning_fabric import LearningFabric
from tests_engine.test_ascendancy_server import ascendancy_genome_http


def prediction(**changes):
    body = dict(producer="psi", asset="NQ", target="direction", prediction="up",
                probability=0.8, reference_value=100.0,
                emitted_at="2026-09-01T14:00:00Z", horizon_seconds=300,
                regime="trend", evidence_ids=["bar:original"], source_commit="a" * 40)
    body.update(changes)
    return body


def test_durable_forecasts_feed_spine_without_replay_or_duplicate_storage(tmp_path):
    learning = LearningFabric(tmp_path)
    p = learning.record_prediction(prediction())["prediction"]
    first = learning.intelligence_snapshot()
    assert first["claim_count"] == 1
    assert first["claims"][0]["stance"] == 1.0
    assert first["claims"][0]["confidence"] == 0.8
    assert first["claims"][0]["details"]["source_commit"] == "a" * 40
    assert first["claims"][0]["details"]["prediction_id"] == p["prediction_id"]
    assert first["claims"][0]["lineage"] == ["bar:original"]
    learning.record_prediction(prediction())
    restored = LearningFabric(tmp_path).intelligence_snapshot(as_of=first["as_of"])
    assert restored == first
    assert restored["execution_authorized"] is False
    assert restored["production_decision_authorized"] is False


def test_first_receipt_time_is_causal_even_for_late_historical_import(tmp_path, monkeypatch):
    learning = LearningFabric(tmp_path)
    monkeypatch.setattr("icarus_engine.learning_fabric._utc_now", lambda: "2026-09-01T14:10:00Z")
    learning.record_prediction(prediction())
    assert learning.intelligence_snapshot(as_of="2026-09-01T14:09:59Z")["claim_count"] == 0
    assert learning.intelligence_snapshot(as_of="2026-09-01T14:10:00Z")["claim_count"] == 1
    learning.record_prediction(prediction(emitted_at="2026-09-01T14:20:00Z"))
    assert learning.intelligence_snapshot(as_of="2026-09-01T14:10:00Z")["claim_count"] == 1
    later = learning.intelligence_snapshot(as_of="2026-09-01T14:25:00Z")
    assert later["claim_count"] == 1
    assert later["feed"]["unprojected"][0]["reason"] == "RECEIPT_PRECEDES_EMISSION"


def test_native_sibyl_harvest_automatically_reaches_spine(tmp_path):
    from icarus_engine.sibyl import SibylEngine
    engine = SibylEngine(tmp_path)
    engine.record_forecast(dict(asset="NQ", observed_at="2026-09-01T14:00:00Z",
                                current_price=100.0, volatility_pct=0.01,
                                horizons=[300], source_commit="c" * 40))
    learning = LearningFabric(tmp_path)
    assert learning.harvest_native()["sibyl"]["forecasts_imported"] == 1
    spine = learning.intelligence_snapshot()
    assert spine["feed"]["prediction_count"] == 1
    assert {c["source"] for c in spine["claims"]} == {"sibyl"}
    assert len(spine["claims"]) >= 2
    assert {c["details"]["source_commit"] for c in spine["claims"]} == {"c" * 40}
    assert all(c["details"]["source_revision_verified"] is False for c in spine["claims"])


def test_revision_label_and_observation_scope_do_not_create_false_consensus(tmp_path):
    learning = LearningFabric(tmp_path)
    learning.record_prediction(prediction())
    learning.record_prediction(prediction(source_commit="b" * 40, prediction="down"))
    learning.record_prediction(prediction(producer="other", prediction="down"))
    spine = learning.intelligence_snapshot()
    assert spine["semantic_group_count"] == 3
    assert not any(g["directional_conflict"] for g in spine["fused_state"])
    assert all(s["predictive_incremental_information"] is None for s in spine["source_contributions"])


def test_numeric_forecasts_are_visible_as_unprojected_and_window_is_bounded(tmp_path):
    learning = LearningFabric(tmp_path)
    learning.record_prediction(prediction(target="numeric", prediction=110.0))
    result = learning.intelligence_snapshot()
    assert result["claim_count"] == 0
    assert result["feed"]["unprojected_count"] == 1
    assert result["feed"]["unprojected"][0]["reason"] == "NUMERIC_HAS_NO_STANCE_CONTRACT"
    learning.record_prediction(prediction(producer="sibyl"))
    result = learning.intelligence_snapshot(limit=1)
    assert result["feed"]["prediction_count"] == 1
    assert result["feed"]["window_limited"] is True
    with pytest.raises(ValueError):
        learning.intelligence_snapshot(limit=501)


def test_settled_outcome_cannot_rewrite_forecast_claim(tmp_path):
    learning = LearningFabric(tmp_path)
    p = learning.record_prediction(prediction())["prediction"]
    before = learning.intelligence_snapshot()
    learning.record_outcome(dict(prediction_id=p["prediction_id"], observed_at="2026-09-01T14:05:00Z",
                                 actual_value=90.0, evidence=["bar:later"]))
    assert learning.intelligence_snapshot(as_of=before["as_of"]) == before


def test_corrupt_forecast_storage_fails_closed(tmp_path):
    learning = LearningFabric(tmp_path)
    learning.record_prediction(prediction())
    with learning._conn:
        learning._conn.execute("UPDATE predictions SET semantic_json='{}'")
    with pytest.raises(RuntimeError, match="forecast storage"):
        learning.intelligence_snapshot()


def test_class_projection_preserves_original_float_probabilities_and_identity(tmp_path):
    learning = LearningFabric(tmp_path)
    p = learning.record_prediction(prediction(target="class", prediction="c0", probabilities={
        "c0": 0.8102172359965896, "c1": 0.9021659504395827, "c2": 0.3101475693193326,
    }))["prediction"]
    snapshot = learning.intelligence_snapshot()
    assert snapshot["claim_count"] == 3
    assert {c["details"]["prediction_id"] for c in snapshot["claims"]} == {p["prediction_id"]}
    assert {c["details"]["label"]: c["confidence"] for c in snapshot["claims"]} == p["probabilities"]


def test_submillisecond_receipt_boundary_has_no_visible_future_claims(tmp_path, monkeypatch):
    learning = LearningFabric(tmp_path)
    monkeypatch.setattr("icarus_engine.learning_fabric._utc_now", lambda: "2026-09-01T14:10:00.000000Z")
    learning.record_prediction(prediction(producer="available"))
    monkeypatch.setattr("icarus_engine.learning_fabric._utc_now", lambda: "2026-09-01T14:10:00.000400Z")
    learning.record_prediction(prediction(producer="not-yet-received"))
    view = learning.intelligence_snapshot(as_of="2026-09-01T14:10:00.000100Z", limit=1)
    assert view["claim_count"] == len(view["claims"]) == 1
    assert {c["source"] for c in view["claims"]} == {"available"}
    assert view["feed"]["prediction_count"] == 1
    assert view["feed"]["window_limited"] is False


def test_valid_ledger_values_outside_spine_limits_remain_visible_as_unprojected(tmp_path):
    learning = LearningFabric(tmp_path)
    learning.record_prediction(prediction(regime="r" * 128))
    learning.record_prediction(prediction(producer="wide-lineage", evidence_ids=["e" * 500]))
    learning.record_prediction(prediction(producer="projectable"))
    view = learning.intelligence_snapshot()
    assert view["claim_count"] == 1
    assert view["feed"]["unprojected_count"] == 2
    assert {r["reason"] for r in view["feed"]["unprojected"]} == {"SPINE_CONTRACT_LIMIT"}


def test_intelligence_api_requires_auth_and_reads_canonical_ledger(ascendancy_genome_http):
    port, server, request = ascendancy_genome_http
    assert request("GET", "/api/ascendancy/intelligence", auth=False)[0] == 401
    server.learning.record_prediction(prediction())
    before = (port.paused, list(port.runners))
    code, result = request("GET", "/api/ascendancy/intelligence")
    assert code == 200 and result["claim_count"] == 1
    assert (port.paused, list(port.runners)) == before
    assert result["feed"]["storage"] == "CANONICAL_LEARNING_LEDGER"
    assert request("GET", "/api/ascendancy/intelligence?limit=501")[0] == 400


def test_corrupt_receipt_returns_controlled_http_error(ascendancy_genome_http):
    _, server, request = ascendancy_genome_http
    server.learning.record_prediction(prediction())
    with server.learning._conn:
        server.learning._conn.execute("UPDATE predictions SET recorded_at='2026-09-01T14:10:00'")
    code, body = request("GET", "/api/ascendancy/intelligence")
    assert code == 500
    assert body["detail"] == "canonical forecast storage integrity failure"


def test_dashboard_executes_feed_fetch_and_escapes_provenance(tmp_path):
    node = shutil.which("node")
    if not node:
        pytest.skip("Node unavailable")
    source = Path(__file__).resolve().parents[1] / "icarus_engine/ascendancy-ui.js"
    probe = tmp_path / "dashboard-feed.cjs"
    probe.write_text("""
const fs = require('fs'), vm = require('vm'), assert = require('assert');
const el = {innerHTML:''}; let unavailable = false; const requests = [];
const spine = {as_of:'2026-09-01T14:10:00Z',claim_count:1,
 feed:{prediction_count:1,window_limited:true},source_contributions:[{source:'sibyl'}],
 claims:[{source:'<script>bad</script>',stance:1,confidence:0.8,
 observed_at:'2026-09-01T14:00:00Z',received_at:'2026-09-01T14:10:00Z',
 details:{asset:'NQ',source_commit:'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'}}]};
const context = {window:{},document:{querySelector:()=>el},
 localStorage:{getItem:()=> 'token'},fetch:async (url,options)=>{
 requests.push(url);assert.strictEqual(options.headers.Authorization,'Bearer token');
 return {ok:!unavailable||!url.endsWith('/intelligence'),status:503,
 json:async()=>url.endsWith('/intelligence')?spine:{}};
}};
vm.runInNewContext(fs.readFileSync(process.argv[2],'utf8'),context);
(async()=>{
 await context.window.loadAscendancy();
 assert(requests.includes('/api/ascendancy/intelligence'));
 assert(el.innerHTML.includes('DURABLE FORECAST FEED'));
 assert(el.innerHTML.includes('&lt;script&gt;bad&lt;/script&gt;'));
 assert(!el.innerHTML.includes('<script>bad</script>'));
 assert(el.innerHTML.includes('window_limited=true'));
 unavailable = true; await context.window.loadAscendancy();
 assert(el.innerHTML.includes('canonical forecast feed did not load'));
 assert(!el.innerHTML.includes('&lt;script&gt;bad&lt;/script&gt;'));
})().catch(e=>{console.error(e);process.exitCode=1;});
""", encoding="utf-8")
    result = subprocess.run([node, str(probe), str(source)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
