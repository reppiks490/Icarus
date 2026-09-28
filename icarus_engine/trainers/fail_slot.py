# Claude (Opus 5.5) — 2026-09-27. Slot 4 per SPEC.md: "Fit only if losers_from_journal returns n_losers >= 30.
# Else skipped." SPEC gives no target or features and forbids inventing them, so with enough losers this slot
# reports that the owner must define the model. Never fits. (losers_from_journal's event notes use the post-hoc
# window around the exit; a predictive fail model would need as-of features at the entry.)
from __future__ import annotations
from icarus_engine.failure.losers import losers_from_journal

MIN_LOSERS = 30

def train(journal, symbol):
    rep = losers_from_journal(journal)
    n = int(rep.get("n_losers") or 0)
    head = {"slot": "fail", "symbol": symbol.upper(), "journal": str(journal), "n_losers": n,
            "execution_authorized": False, "accuracy_guaranteed": False}
    if n < MIN_LOSERS:
        return {**head, "status": "skipped", "reason": f"{n} losers < {MIN_LOSERS}"}
    return {**head, "status": "blocked",
            "reason": "SPEC.md defines no target or features for Slot 4; the owner must define them before "
                      "anything is fitted"}
