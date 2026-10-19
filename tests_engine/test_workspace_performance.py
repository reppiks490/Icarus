import math
from types import SimpleNamespace

import pytest

from icarus_engine.runtime import Journal
from icarus_engine.workspace_performance import snapshot

DAY = 86400
NOW = 100 * DAY + 3600


@pytest.fixture
def journal(tmp_path):
    j = Journal(str(tmp_path / 'paper.sqlite'))
    yield j
    j.close()


def close(j, profit, day, *, live=True, symbol='REMOVED', run=1):
    j.run_id = run
    ts = day * DAY + 300
    t = SimpleNamespace(entry_id=str(day), direction=1, qty=1, entry_price=100,
                        entry_ts=ts - 60, exit_price=101, exit_ts=ts,
                        exit_comment='paper close', profit=profit)
    j.add_trade(symbol, t, live)


def test_all_runs_removed_assets_and_warmup_exclusion(journal):
    close(journal, 10, 96, run=1)
    close(journal, -3, 98, run=2)
    close(journal, 999, 97, live=False)
    r = snapshot(journal, as_of_ts=NOW)
    assert r['paper_only'] is True
    assert r['execution_authorized'] is False
    assert r['available']
    assert r['realized_pnl'] == 7
    assert r['closed_pieces'] == 2
    assert [x['profit'] for x in r['trades']] == [10, -3]
    assert r['equity_curve'][-1]['realized_pnl'] == 7
    assert r['ratios']['sharpe'] is None
    assert r['ratios']['reason'] == 'CAPITAL_UNAVAILABLE'
    assert r['historical']['mean_closure_pnl'] == 3.5
    assert r['historical']['max_realized_drawdown'] == 3
    assert r['historical']['predictive'] is False


def test_ratios_closed_utc_days_and_zero_gaps(journal):
    for day in range(70, 100):
        if day != 80:
            close(journal, 10 if day % 2 else -5, day)
    close(journal, 9000, 100)
    r = snapshot(journal, as_of_ts=NOW, capital=10000)
    returns = [(0 if day == 80 else 10 if day % 2 else -5) / 10000 for day in range(70, 100)]
    mean = sum(returns) / len(returns)
    variance = sum((v - mean) ** 2 for v in returns) / (len(returns) - 1)
    assert r['ratios']['sample_days'] == 30
    assert r['ratios']['sharpe'] == pytest.approx(mean / math.sqrt(variance) * math.sqrt(365))
    assert r['ratios']['sortino'] == pytest.approx(mean / math.sqrt(sum(min(v, 0) ** 2 for v in returns) / 30) * math.sqrt(365))
    assert r['daily_activity'][10]['closed_pieces'] == 0
    assert r['daily_activity'][-1]['partial_day'] is True
    assert r['realized_pnl'] == sum(returns) * 10000 + 9000


def test_empty_has_no_fake_ratios_or_observation_days(journal):
    r = snapshot(journal, as_of_ts=NOW, capital=1000)
    assert r['realized_pnl'] == 0
    assert r['ratios']['sample_days'] == 0
    assert r['ratios']['sharpe'] is None
    assert r['equity_curve'] == []


def test_limits_bound_views_not_accounting(journal):
    for day in range(50, 100):
        close(journal, day, day)
    r = snapshot(journal, as_of_ts=NOW, capital=1000, max_points=3, trade_limit=2)
    assert r['realized_pnl'] == sum(range(50, 100))
    assert r['closed_pieces'] == 50
    assert len(r['trades']) == 2
    assert len(r['equity_curve']) == 3
    assert r['equity_curve'][-1]['realized_pnl'] == sum(range(50, 100))
    assert r['ratios']['sample_days'] == 50
    assert r['display']['trades_truncated'] is True


@pytest.mark.parametrize('field,value', [('profit', float('inf')), ('profit', None), ('exit_ts', NOW + 1), ('entry_ts', -1), ('exit_ts', 'bad'), ('live', 2)])
def test_bad_persisted_trade_fails_closed(journal, field, value):
    close(journal, 10, 99)
    journal.con.execute(f'UPDATE trades SET {field}=?', (value,))
    journal.con.commit()
    r = snapshot(journal, as_of_ts=NOW, capital=1000)
    assert not r['available']
    assert r['realized_pnl'] is None
    assert r['ratios']['sharpe'] is None


def test_tied_closures_order_by_persisted_id(journal):
    close(journal, 1, 99, symbol='A')
    close(journal, 2, 99, symbol='B')
    assert [x['symbol'] for x in snapshot(journal, as_of_ts=NOW)['trades']] == ['A', 'B']


@pytest.mark.parametrize('kwargs', [{'capital': True}, {'capital': 0}, {'capital': float('nan')}, {'as_of_ts': True}, {'as_of_ts': -1}, {'trade_limit': False}, {'max_points': 1}, {'trade_limit': 10001}])
def test_bad_parameters_raise(journal, kwargs):
    with pytest.raises(ValueError):
        snapshot(journal, **kwargs)


def test_no_losses_or_variance_means_no_infinite_ratio(journal):
    for day in range(70, 100):
        close(journal, 2, day)
    r = snapshot(journal, as_of_ts=NOW, capital=1000)
    assert r['ratios']['sharpe'] is None
    assert r['ratios']['sortino'] is None


def test_reads_do_not_write_and_closed_journal_fails_closed(journal):
    close(journal, 10, 99)
    before = journal.con.total_changes
    snapshot(journal, as_of_ts=NOW)
    assert journal.con.total_changes == before
    journal.close()
    assert snapshot(journal, as_of_ts=NOW)['reason'] == 'JOURNAL_CLOSED'


def test_oversized_ledger_and_observation_range_are_explicit(journal, monkeypatch):
    from icarus_engine import workspace_performance as perf
    close(journal, 1, 90)
    close(journal, 1, 99)
    monkeypatch.setattr(perf, '_MAX_ROWS', 1)
    assert snapshot(journal, as_of_ts=NOW)['reason'] == 'LEDGER_TOO_LARGE'
    monkeypatch.setattr(perf, '_MAX_ROWS', 10)
    monkeypatch.setattr(perf, '_MAX_DAYS', 3)
    assert snapshot(journal, as_of_ts=NOW)['reason'] == 'OBSERVATION_RANGE_TOO_LARGE'


def test_insufficient_days_with_capital_and_zero_downside(journal):
    close(journal, 1, 99)
    r = snapshot(journal, as_of_ts=NOW, capital=100)
    assert r['ratios']['reason'] == 'INSUFFICIENT_SAMPLE'
    for day in range(70, 99):
        close(journal, day, day)
    r = snapshot(journal, as_of_ts=NOW, capital=100)
    assert math.isfinite(r['ratios']['sharpe'])
    assert r['ratios']['sortino'] is None
    assert r['ratios']['reason'] == 'ZERO_RISK_DENOMINATOR'


def test_realized_drawdown_computed_before_display_sampling(journal):
    close(journal, 10, 96)
    close(journal, -40, 97)
    close(journal, 50, 98)
    r = snapshot(journal, as_of_ts=NOW, max_points=2)
    assert r['historical']['max_realized_drawdown'] == 40
    assert r['equity_curve'][-1]['realized_pnl'] == 20


@pytest.mark.parametrize('field,value', [
    ('qty', 0), ('qty', 1.5), ('qty', 'bad'), ('direction', 0),
    ('direction', 1.5), ('entry_price', None), ('entry_price', float('inf')),
    ('exit_price', None), ('exit_price', 'bad'), ('bars', -1), ('bars', 2.5),
    ('piece', -1), ('run_id', -1), ('lot_id', -1), ('entry_qty', -1),
    ('entry_ts', 99 * DAY + .5), ('exit_ts', 99 * DAY + .5),
    ('entry_id', None), ('entry_id', ''), ('exit_comment', b'bytes'),
])
def test_malformed_rendered_fields_fail_closed(journal, field, value):
    close(journal, 10, 99)
    journal.con.execute(f'UPDATE trades SET {field}=?', (value,))
    journal.con.commit()
    r = snapshot(journal, as_of_ts=NOW, capital=1000)
    assert r['available'] is False
    assert r['reason'] == 'INVALID_PERSISTED_TRADE'
    assert r['paper_only'] is True
    assert r['execution_authorized'] is False
    assert r['trades'] == []


def test_finite_negative_and_zero_futures_prices_are_preserved(journal):
    # Energy futures can legitimately trade below zero; recorded prices are not
    # a positive-price admission gate for historical closure accounting.
    close(journal, 10, 99, symbol='CL')
    journal.con.execute('UPDATE trades SET entry_price=-10, exit_price=0')
    journal.con.commit()
    result = snapshot(journal, as_of_ts=NOW, capital=1000)
    assert result['available'] is True
    assert result['trades'][0]['entry_price'] == -10
    assert result['realized_pnl'] == 10
