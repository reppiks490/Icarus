"""Offline market-bar admission and lossless aggregation contracts."""
from types import SimpleNamespace

import pytest

from icarus_engine.feeds.bars import FileFeed
from icarus_engine.feeds.databento import Databento
from icarus_engine.pine.timeframe import Bar


@pytest.mark.parametrize('target', [180, 300])
def test_coarse_source_cannot_be_split_across_target_boundaries(target):
    feed = FileFeed([Bar(t, 100, 110, 90, 105, 1) for t in [0, 120, 240, 360]])
    assert feed.candles('NQ', target, 0, 600) == []


def test_phase_shifted_source_cannot_leak_future_prices_into_previous_bucket():
    feed = FileFeed([Bar(t, 100, 110, 90, 105, 1) for t in [60, 180, 300]])
    assert feed.candles('NQ', 240, 0, 600) == []


def test_aligned_integer_multiple_preserves_prices_and_volume():
    feed = FileFeed([Bar(t, 100, 110, 90, 105, 1) for t in [0, 120, 240, 360]])
    bars = feed.candles('NQ', 240, 0, 480)
    assert [(b.ts, b.o, b.h, b.l, b.c, b.v) for b in bars] == [
        (0, 100, 110, 90, 105, 2), (240, 100, 110, 90, 105, 2),
    ]


@pytest.mark.parametrize('override', [
    {'low': 120_000_000_000}, {'open': 120_000_000_000}, {'close': 80_000_000_000},
    {'volume': -1}, {'volume': float('nan')}, {'volume': float('inf')},
])
def test_databento_rejects_impossible_bar_geometry_or_volume(override):
    data = dict(ts_event=1_000_000_000, open=100_000_000_000, high=110_000_000_000,
                low=90_000_000_000, close=105_000_000_000, volume=10)
    data.update(override)
    with pytest.raises(ValueError, match='OHLC|volume'):
        Databento._ohlcv_record(SimpleNamespace(**data))


def test_valid_negative_market_prices_are_not_rejected():
    bar = Databento._ohlcv_record(SimpleNamespace(
        ts_event=1_000_000_000, open=-20_000_000_000, high=-10_000_000_000,
        low=-30_000_000_000, close=-15_000_000_000, volume=1,
    ))
    assert (bar.o, bar.h, bar.l, bar.c, bar.v) == (-20, -10, -30, -15, 1)
