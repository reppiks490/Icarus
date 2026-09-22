# Grok (xAI) — 2026-09-22. Whole file. Frozen contracts. Astra implements XGB against these names.
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
LABEL = "y"  # next-bar sign on THIS family index: -1 or +1. Never 0.

WALK = {"train": 0.60, "valid": 0.20, "holdout": 0.20, "shuffle": False}
XGB_CLASSIFIER = {
    "objective": "binary:logistic",
    "tree_method": "hist",
    "max_depth": 4,
    "eta": 0.05,
    "subsample": 0.8,
    "colsample_bytree": 0.8,
    "min_child_weight": 8,
    "lambda": 1.0,
    "n_estimators": 400,
    "early_stopping_rounds": 40,
    "eval_metric": "logloss",
    "seed": 7,
}
CALIBRATE = "isotonic"  # holdout only. Never fit on train.
ARTIFACT = "run/trainers/{sym}_{family}_{slot}.json"
SLOTS = {
    "logit": "slot0 baseline",
    "xgb": "slot1 primary",
    "rank": "slot2 candidate ranker",
    "regime": "slot3",
    "fail": "slot4",
}
# Official swap is a JSON file. It does not call Pulse.
SWAP_YES = {"min_overlap": 200, "min_sign_agree": 0.55, "min_macro_agree": 0.55}
SWAP_SCHEMA = (
    "status", "execution", "candidate", "family", "overlap",
    "sign_agree", "tide_agree", "macro_agree", "xgb_artifact",
    "swap_recommend", "execution_authorized",
)

def artifact(sym: str, family: str, slot: str = "xgb") -> str:
    return ARTIFACT.format(sym=sym.upper(), family=family, slot=slot)
