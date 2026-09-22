# Grok (xAI) — 2026-09-22. Whole file.
from __future__ import annotations
from icarus_engine.spec import IGNORED

DO_NOT_TRADE = frozenset(s for s in IGNORED if s != "ETHUSD") | frozenset({"ETH"})
DO_NOT_TRADE_NAMES = frozenset({
    "MBT", "MBT1!", "MBT=F", "CME:MBT1!",
    "SOL", "SOLUSD", "SOL-USD", "COINBASE:SOLUSD",
    "ETH", "ETHUSD", "ETH-USD", "COINBASE:ETHUSD",
})

def ignored_symbol(token: str) -> bool:
    raw = (token or "").strip().upper()
    if raw in DO_NOT_TRADE or raw in DO_NOT_TRADE_NAMES or raw in IGNORED:
        return True
    tail = raw.split(":")[-1].replace("-USD", "").replace("USD", "")
    return tail in DO_NOT_TRADE

def assert_tradable(token: str) -> None:
    if ignored_symbol(token):
        raise ValueError(f"{token} is ignored: MBT, SOL, ETH/ETHUSD are not traded")
