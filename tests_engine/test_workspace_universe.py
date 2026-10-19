from icarus_engine import assets


def test_expanded_selection_preserves_original_launcher_and_all_ten_families():
    from icarus_engine.workspace_universe import ORIGINAL_ASSETS, dashboard_assets, universe
    original = {'NQ','BTC','MNQ','MES','ES','YM','MYM','RTY','M2K','GC','MGC','SI','SIL','PL','PA','MBT'}
    assert set(ORIGINAL_ASSETS) == original
    selected = dashboard_assets()
    assert original <= set(selected)
    assert {'CL','NG','HG','6E','6J','6B','6A','ZN','ZB','BTCF'} <= set(selected)
    assert {'MCL','MNG','MHG','M6E','MJY','M6B','M6A','MBT'} <= set(selected)
    assert len(selected) == len(set(selected))
    assert all(symbol in assets.REGISTRY for symbol in selected)
    rows = universe()['families']
    assert len(rows) == 10
    assert next(row for row in rows if row['root'] == 'CL')['micros'] == ['MCL']
    assert next(row for row in rows if row['root'] == 'ZN')['micros'] == []
    assert all(row['execution_authorized'] is False for row in rows)


def test_universe_does_not_invent_feed_or_profitability_qualification():
    from icarus_engine.workspace_universe import universe
    result = universe()
    assert result['fresh_feed_access_verified'] is False
    assert result['profitability_verified'] is False
    assert result['execution_authorized'] is False
    assert result['original_asset_count'] == 16
    for row in result['families']:
        assert row['point_value'] > 0
        assert row['tick_value'] > 0
        assert row['data_status'] == 'REQUIRES_FEED_OBSERVATION'
