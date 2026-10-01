# Grok (xAI) — 2026-09-22. Whole file. Frozen contracts.
from __future__ import annotations

TRADED = ("NQ", "ES", "YM", "GC", "SI", "PL", "PA", "BTCF", "BTC")
IGNORED = ("MBT", "SOL", "ETH", "ETHUSD")
FAMILIES = (
    "clock_minutes", "clock_hours", "clock_seconds",
    "clock_daily", "clock_weekly", "renko", "range", "tick",
)
FEATURE_KEYS = (
    "ret_1", "ret_3", "body", "range", "close_loc", "tide", "run", "fomc", "any_macro",
)
OPTIONAL_KEYS = ("cpi", "nfp", "earnings", "vix_z", "tnx_z", "dxy_z")
LABEL = "y"
WALK = {"train": 0.60, "valid": 0.20, "holdout": 0.20, "shuffle": False}
XGB_CLASSIFIER = {
    "objective": "binary:logistic", "tree_method": "hist", "max_depth": 4,
    "eta": 0.05, "subsample": 0.8, "colsample_bytree": 0.8,
    "min_child_weight": 8, "lambda": 1.0, "n_estimators": 400,
    "early_stopping_rounds": 40, "eval_metric": "logloss", "seed": 7,
}
CALIBRATE = "isotonic"
ARTIFACT = "run/trainers/{sym}_{family}_{slot}.json"
SLOTS = {"logit": "slot0", "xgb": "slot1", "rank": "slot2", "regime": "slot3", "fail": "slot4"}
SWAP_YES = {"min_overlap": 200, "min_sign_agree": 0.55, "min_macro_agree": 0.55}
CSV_REPO = "https://github.com/reppiks490/multi-level-csv.git"
BATCHES = (
    "Csv first 60.zip", "First 60 half.zip", "Csv 2nd 60.zip",
    "2nd 60 half.zip", "Csv last 57.zip", "Last 57 half.zip",
)

def artifact(sym: str, family: str, slot: str = "xgb") -> str:
    return ARTIFACT.format(sym=sym.upper(), family=family, slot=slot)
