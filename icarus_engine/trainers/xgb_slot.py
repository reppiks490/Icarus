# Grok (xAI) — 2026-09-22. Slot 1 contract. Astra fills fit() using spec.XGB_CLASSIFIER.
from __future__ import annotations
from icarus_engine.spec import FEATURE_KEYS, XGB_CLASSIFIER, CALIBRATE

def params():
    return dict(XGB_CLASSIFIER)

def fit(rows):
    try:
        import xgboost  # noqa: F401
    except ImportError:
        return {"status": "blocked", "reason": "pip install -e '.[ml]'", "params": params(),
                "features": list(FEATURE_KEYS), "calibrate": CALIBRATE}
    raise NotImplementedError(
        "Astra: fit XGBClassifier with spec.XGB_CLASSIFIER on FEATURE_KEYS; "
        "isotonic on holdout only; write artifact() path"
    )
