# Grok (xAI) — 2026-09-22.
from icarus_engine.spec import FEATURE_KEYS, IGNORED, TRADED, XGB_CLASSIFIER, artifact
from icarus_engine.trainers.dataset import attach_labels

def test_feature_keys_match_dataset():
    bars = []
    px = 100.0
    for i in range(50):
        px += 0.2
        bars.append({"ts": 1_700_000_000 + i * 60, "open": px, "high": px + 0.3,
                     "low": px - 0.3, "close": px, "tide_long": 1.0, "tide_short": 0.0})
    row = attach_labels(bars, "clock_minutes")[0]
    assert tuple(row["x"].keys()) == FEATURE_KEYS

def test_artifact_name():
    assert artifact("nq", "clock_minutes") == "run/trainers/NQ_clock_minutes_xgb.json"

def test_universe():
    assert "ETHUSD" in IGNORED and "NQ" in TRADED
    assert XGB_CLASSIFIER["max_depth"] == 4 and XGB_CLASSIFIER["tree_method"] == "hist"
