# Grok (xAI) — 2026-09-22.
from icarus_engine.ignore_trade import DO_NOT_TRADE, assert_tradable, ignored_symbol


def test_owner_ignore_set():
    assert DO_NOT_TRADE == {"MBT", "SOL", "ETH"}
    for name in ("MBT", "MBT1!", "SOL", "SOL-USD", "ETH", "ETHUSD", "COINBASE:ETHUSD"):
        assert ignored_symbol(name)
    for name in ("NQ", "ES", "YM", "GC", "SI", "BTC", "BTCF"):
        assert not ignored_symbol(name)


def test_assert_tradable_blocks_ignored():
    try:
        assert_tradable("ETHUSD")
    except ValueError as exc:
        assert "not be traded" in str(exc)
        return
    raise AssertionError("ETHUSD must raise")
