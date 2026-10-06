from __future__ import annotations

from icarus_engine.overview_command_center import command_center_snapshot, research_fabric_snapshot


def test_research_fabric_snapshot_never_exposes_secret_values(monkeypatch):
    monkeypatch.setenv("DATABENTO_API_KEY", "primary-secret")
    monkeypatch.setenv("DATABENTO_API_KEY_SECONDARY", "secondary-secret")
    monkeypatch.setenv("DATABENTO_API_KEY_THIRD", "third-secret")
    monkeypatch.setenv("FRED_API_KEY", "fred-secret")
    monkeypatch.setenv("FMP_API_KEY", "fmp-secret")
    monkeypatch.setenv("TIINGO_API_TOKEN", "tiingo-secret")
    monkeypatch.setenv("EODHD_API_TOKEN", "eod-secret")
    monkeypatch.setenv("ALPACA_API_KEY", "alpaca-key")
    monkeypatch.setenv("ALPACA_SECRET_KEY", "alpaca-secret")
    monkeypatch.setenv("EXA_API_KEY", "exa-secret")

    documents = {
        "databento_depth_sweep_primary.json": {
            "status": "OK", "held_days": ["2026-10-01"], "spent_usd": 2.0, "cap_usd": 5.0
        },
        "databento_depth_sweep_secondary.json": {
            "status": "OK", "held_days": ["2026-10-01"], "spent_usd": 1.0, "cap_usd": 4.0
        },
        "databento_depth_sweep_third.json": {
            "status": "OK", "held_days": ["2026-10-01"], "spent_usd": 3.0, "cap_usd": 8.0
        },
        "databento_depth_corpus_index.json": {
            "status": "OK", "cached_slices": 18, "lane": {"spent_usd": 90.0, "cap_usd": 93.0}
        },
        "databento_depth_corpus_diversifier.json": {
            "status": "OK", "cached_slices": 22, "lane": {"spent_usd": 94.0, "cap_usd": 95.0}
        },
        "fred_alfred_manifest.json": {
            "generated_at": "2026-10-05T00:00:00Z",
            "series": {"DGS10": {"status": "ok"}, "DFF": {"status": "ok"}},
        },
        "external_data_fabric.json": {
            "generated_at": "2026-10-05T00:00:00Z",
            "providers": {
                "fmp": {"status": "ok"},
                "tiingo": {"status": "partial"},
                "eodhd": {"status": "ok"},
            },
            "summary": {"universe": ["QQQ", "SPY"]},
        },
    }

    def fetch(url: str):
        return documents[url.rsplit("/", 1)[-1]]

    snap = research_fabric_snapshot(fetch_json=fetch, force=True)
    assert len(snap["databento_accounts"]) == 3
    assert all(row["evidence_present"] for row in snap["databento_accounts"])
    assert snap["fred"]["series_ok"] == 2
    assert snap["external_data"]["provider_status"]["tiingo"] == "partial"
    assert all(row["configured"] for row in snap["providers"])
    raw = repr(snap)
    for secret in (
        "primary-secret", "secondary-secret", "third-secret", "fred-secret",
        "fmp-secret", "tiingo-secret", "eod-secret", "alpaca-secret", "exa-secret",
    ):
        assert secret not in raw
    assert all(row["secret_value_exposed"] is False for row in snap["providers"])
    assert snap["execution_authorized"] is False


def test_command_center_gauges_use_observed_evidence_and_remain_research_only():
    validation = {
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
    }
    market = {
        "assets": [
            {
                "symbol": "NQ", "warm": True, "last_error": "", "poll_age": 5.0,
                "state": {
                    "rate_regime": 0.82,
                    "votes": [{"l": True, "s": False}, {"l": True, "s": False}, {"l": False, "s": True}],
                    "eff_thresh": 3.0, "final_l": 2.7, "final_s": 0.9, "entry_allowed": True,
                },
            },
            {
                "symbol": "ES", "warm": True, "last_error": "", "poll_age": 6.0,
                "state": {
                    "rate_regime": 0.74,
                    "votes": [{"l": False, "s": True}, {"l": False, "s": True}],
                    "eff_thresh": 2.5, "final_l": 0.5, "final_s": 2.0, "entry_allowed": True,
                },
            },
        ]
    }
    audit = {
        "status": "green",
        "summary": {"current_head_failures": 0, "unresolved": 0},
        "loops": [{"status": "RUN_PERSISTED"} for _ in range(5)],
        "loop_sync": {"status": "green"},
    }
    brain = {
        "candidates": [{
            "candidate_id": "nq-edge-v1",
            "stage": "qualified_shadow",
            "validation": validation,
        }],
        "performance_proof": {
            "candidate_statistics": [{
                "candidate_id": "nq-edge-v1",
                "settled": 30,
                "outcome_coverage": 1.0,
                "success_rate": 0.73,
                "brier_score": 0.18,
                "closed_regime_sample": True,
            }],
            "regime_champions": [{"shadow_champion": "nq-edge-v1"}],
        },
    }
    fabric = {
        "documents_available": ["a", "b"],
        "errors": {},
        "providers": [],
        "databento_accounts": [
            {"manifest_present": True, "status": "ok", "evidence_present": True, "cached_slices": 20, "held_days": 4},
            {"manifest_present": True, "status": "ok", "evidence_present": True, "cached_slices": 30, "held_days": 4},
            {"manifest_present": True, "status": "ok", "evidence_present": True, "cached_slices": 40, "held_days": 4},
        ],
        "fred": {},
        "external_data": {},
    }

    out = command_center_snapshot(market, audit, brain, fabric)
    gauges = {row["label"]: row for row in out["gauges"]}
    assert gauges["Edge Emergence"]["score"] is not None
    assert gauges["Champion Readiness"]["score"] is not None
    assert gauges["Regime Clarity"]["score"] == 78
    assert gauges["Signal Consensus"]["score"] > 70
    assert gauges["Microstructure Coverage"]["score"] == 100
    assert gauges["Automation Health"]["score"] == 100
    assert gauges["Paper Execution Readiness"]["score"] == 100
    assert gauges["Opportunity Pressure"]["score"] == 90
    assert out["authority"]["research_only"] is True
    assert out["authority"]["execution_authorized"] is False
    assert out["authority"]["production_decision_authorized"] is False


def test_command_center_refuses_to_invent_edge_or_champion_scores():
    out = command_center_snapshot({"assets": []}, {}, {}, {})
    gauges = {row["label"]: row for row in out["gauges"]}
    assert gauges["Edge Emergence"]["score"] is None
    assert gauges["Edge Emergence"]["state"] == "INSUFFICIENT_EVIDENCE"
    assert gauges["Champion Readiness"]["score"] is None
    assert gauges["Champion Readiness"]["state"] == "INSUFFICIENT_EVIDENCE"
