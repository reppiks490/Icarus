from icarus_engine import paper_workspaces
from icarus_engine.pine.timeframe import Bar


def test_shared_feed_candle_cache_fetches_only_uncovered_ranges():
    class Feed:
        def __init__(self):
            self.calls = []

        def candles(self, symbol, granularity, start_ts, end_ts):
            self.calls.append((symbol, granularity, start_ts, end_ts))
            return [
                Bar(ts, 1.0, 2.0, 0.5, 1.5, 10.0)
                for ts in range(start_ts - granularity, end_ts + granularity, granularity)
            ]

    raw = Feed()
    shared = paper_workspaces.SharedFeed(raw)
    assert [bar.ts for bar in shared.candles("NQ", 60, 0, 180)] == [0, 60, 120]
    assert [bar.ts for bar in shared.candles("NQ", 60, 60, 240)] == [60, 120, 180]
    assert raw.calls == [("NQ", 60, 0, 180), ("NQ", 60, 180, 240)]


def test_shared_feed_does_not_cache_out_of_range_provider_rows():
    class Feed:
        def candles(self, _symbol, _granularity, start_ts, end_ts):
            return [
                Bar(ts, 1.0, 2.0, 0.5, 1.5, 10.0)
                for ts in range(start_ts - 60, end_ts + 60, 60)
            ]

    shared = paper_workspaces.SharedFeed(Feed())
    assert [bar.ts for bar in shared.candles("NQ", 60, 60, 180)] == [60, 120]
