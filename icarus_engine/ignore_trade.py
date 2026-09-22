# Grok (xAI) — 2026-09-22. Whole file.
"""Owner: MBT, SOL, Coinbase ETHUSD do not appear in the engine and must not be traded."""
from __future__ import annotations

# Canonical REGISTRY symbols.
DO_NOT_TRADE = frozenset({"MBT", "SOL", "ETH"})
# Names that must resolve into the same ignore set.
DO_NOT_TRADE_NAMES = frozenset({
    "MBT", "MBT1!", "MBT=F", "CME:MBT1!",
    "SOL", "SOLUSD", "SOL-USD", "COINBASE:SOLUSD",
    "ETH", "ETHUSD", "ETH-USD", "COINBASE:ETHUSD",
})


def ignored_symbol(token: str) -> bool:
    raw = (token or "").strip().upper()
    if raw in DO_NOT_TRADE or raw in DO_NOT_TRADE_NAMES:
        return True
    tail = raw.split(":")[-1]
    tail = tail.replace("-USD", "").replace("USD", "")
    return tail in DO_NOT_TRADE


def assert_tradable(token: str) -> None:
    if ignored_symbol(token):
        raise ValueError(
            f"{token} is ignored: MBT, SOL, and ETH/ETHUSD are not in the engine and must not be traded"
        )
