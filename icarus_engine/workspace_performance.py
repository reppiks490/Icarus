"""Read-only performance of persisted post-cutover paper closure pieces.

This is realized closure P&L, not broker equity, mark-to-market equity, or a
prediction. All process runs and symbols are included; replay rows are excluded.
"""
from __future__ import annotations

import math
import sqlite3
import statistics
import time
from datetime import datetime, timezone

_DAY = 86400
_MIN_DAYS = 20
_MAX_ROWS = 100000
_MAX_DAYS = 36600
_COLUMNS = ('id', 'symbol', 'entry_id', 'direction', 'qty', 'entry_price',
            'entry_ts', 'exit_price', 'exit_ts', 'exit_comment', 'profit',
            'piece', 'run_id', 'lot_id', 'entry_qty', 'bars')


def _finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def _bounded_int(name, value, minimum, maximum):
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError(f'{name} must be an integer between {minimum} and {maximum}')


def _date(day):
    return datetime.fromtimestamp(day * _DAY, timezone.utc).date().isoformat()


def _sample(items, limit):
    if len(items) <= limit:
        return items
    return [items[i * (len(items) - 1) // (limit - 1)] for i in range(limit)]


def read_persisted_trades(journal, *, as_of_ts):
    """Validate every persisted paper closure before any accounting aggregation.

    A malformed row invalidates this ledger, rather than being omitted or
    coerced by SQL. Callers supply their common observation clock. The returned
    rows are detached under the journal owner lock and contain all runs/symbols.
    """
    now = as_of_ts
    if not _finite(now) or not 0 < now < 253402214400:
        raise ValueError('as_of_ts must be finite positive UTC epoch seconds')
    try:
        with journal._lock:
            if journal._closed:
                return [], 'JOURNAL_CLOSED'
            malformed_live = journal.con.execute(
                "SELECT COUNT(*) FROM trades WHERE live IS NULL OR typeof(live)!='integer' OR live NOT IN (0,1)"
            ).fetchone()[0]
            if malformed_live:
                return [], 'INVALID_LIVE_FLAG'
            raw = journal.con.execute(
                f"SELECT {','.join(_COLUMNS)} FROM trades WHERE live=1 ORDER BY exit_ts,id LIMIT ?",
                (_MAX_ROWS + 1,)
            ).fetchall()
    except (sqlite3.Error, AttributeError):
        return [], 'JOURNAL_READ_FAILED'
    if len(raw) > _MAX_ROWS:
        return [], 'LEDGER_TOO_LARGE'
    trades = []
    for values in raw:
        row = dict(zip(_COLUMNS, values))
        entry, exit_, profit = row['entry_ts'], row['exit_ts'], row['profit']
        integer_fields = {'id': 1, 'qty': 1, 'piece': 0, 'run_id': 0,
                          'lot_id': 0, 'entry_qty': 0, 'bars': 0}
        invalid_integer = any(type(row[key]) is not int or row[key] < minimum
                              for key, minimum in integer_fields.items())
        if (invalid_integer
                or type(row['direction']) is not int or row['direction'] not in (-1, 1)
                or type(entry) is not int or type(exit_) is not int
                or not _finite(profit) or not 0 < entry <= exit_ <= now
                or any(not _finite(row[key])
                       for key in ('entry_price', 'exit_price'))
                or not isinstance(row['symbol'], str) or not row['symbol'].strip()
                or not isinstance(row['entry_id'], str) or not row['entry_id'].strip()
                or (row['exit_comment'] is not None and not isinstance(row['exit_comment'], str))):
            return [], 'INVALID_PERSISTED_TRADE'
        trades.append(row)
    return trades, None


def snapshot(journal, *, as_of_ts=None, capital=None, max_points=400, trade_limit=100):
    """Snapshot a runtime.Journal without writes or filtering by current assets.

    Ratios use complete UTC calendar days within the observed closure range,
    including zero-closure gap days. Daily return proxies divide realized P&L
    by supplied fixed configured simulated capital (not historical account NAV).
    Annualization is sqrt(365), sample Sharpe standard deviation, and Sortino
    downside RMS about zero over all observed days. No risk-free rate is assumed.
    Missing capital, fewer than 20 complete days, or zero denominators yield null.
    Display sampling never truncates accounting or ratio calculations. Oversized
    ledgers/ranges and invalid post-cutover rows explicitly fail closed.
    """
    now = time.time() if as_of_ts is None else as_of_ts
    if not _finite(now) or not 0 < now < 253402214400:
        raise ValueError('as_of_ts must be finite positive UTC epoch seconds')
    if capital is not None and (not _finite(capital) or capital <= 0):
        raise ValueError('capital must be finite positive configured simulated capital')
    _bounded_int('max_points', max_points, 2, 10000)
    _bounded_int('trade_limit', trade_limit, 1, 10000)
    ratios = {'sharpe': None, 'sortino': None, 'sample_days': 0,
              'minimum_days': _MIN_DAYS, 'annualization_days': 365,
              'capital': capital, 'reason': 'INSUFFICIENT_SAMPLE',
              'basis': 'Closed UTC calendar-day realized paper P&L / fixed configured simulated capital; zero risk-free rate; not mark-to-market returns',
              'capital_basis': 'Current configured simulated capital held fixed for the entire observation range; historical deposits and NAV are not reconstructed',
              'sharpe_denominator': 'Sample standard deviation (ddof=1)',
              'sortino_denominator': 'Root mean squared negative daily return about zero over all sample days'}
    result = {'schema_version': 1, 'available': False, 'status': 'UNAVAILABLE',
              'reason': None, 'as_of_ts': now,
              'paper_only': True, 'execution_authorized': False,
              'basis': 'Persisted realized paper closure P&L across all runs and symbols; live=1 excludes warmup/replay; closure pieces are not complete position round trips',
              'realized_pnl': None, 'closed_pieces': None, 'last_close_ts': None,
              'trades': [], 'equity_curve': [], 'daily_activity': [],
              'ratios': ratios, 'historical': {'predictive': False},
              'display': {'max_points': max_points, 'trade_limit': trade_limit,
                          'trades_truncated': False, 'equity_sampled': False,
                          'daily_sampled': False},
              'limits': {'maximum_ledger_rows': _MAX_ROWS, 'maximum_observation_days': _MAX_DAYS}}

    def unavailable(reason):
        result['reason'] = reason
        ratios['reason'] = reason
        return result

    valid_trades, reason = read_persisted_trades(journal, as_of_ts=now)
    if reason:
        return unavailable(reason)
    trades = []
    daily = {}
    cumulative = 0.0
    peak = 0.0
    max_drawdown = 0.0
    curve = []
    profits = []
    for row in valid_trades:
        exit_, profit = row['exit_ts'], row['profit']
        cumulative += profit
        if not math.isfinite(cumulative):
            return unavailable('NONFINITE_AGGREGATE')
        peak = max(peak, cumulative)
        max_drawdown = max(max_drawdown, peak - cumulative)
        if not math.isfinite(max_drawdown):
            return unavailable('NONFINITE_AGGREGATE')
        day = int(exit_ // _DAY)
        aggregate = daily.setdefault(day, {'profit': 0.0, 'count': 0})
        aggregate['profit'] += profit
        aggregate['count'] += 1
        if not math.isfinite(aggregate['profit']):
            return unavailable('NONFINITE_AGGREGATE')
        curve.append({'ts': exit_, 'trade_id': row['id'], 'realized_pnl': cumulative})
        trades.append(row)
        profits.append(profit)
    days = []
    if daily:
        first, last = min(daily), max(daily)
        if last - first + 1 > _MAX_DAYS:
            return unavailable('OBSERVATION_RANGE_TOO_LARGE')
        for day in range(first, last + 1):
            aggregate = daily.get(day, {'profit': 0.0, 'count': 0})
            days.append({'date': _date(day), 'ts': day * _DAY,
                         'realized_pnl': aggregate['profit'], 'closed_pieces': aggregate['count'],
                         'partial_day': day >= int(now // _DAY)})
    complete = [day['realized_pnl'] for day in days if not day['partial_day']]
    ratios['sample_days'] = len(complete)
    ratios['observation_start'] = days[0]['date'] if days else None
    ratios['observation_end'] = days[-1]['date'] if days else None
    if capital is None:
        ratios['reason'] = 'CAPITAL_UNAVAILABLE'
    elif len(complete) >= _MIN_DAYS:
        returns = [profit / capital for profit in complete]
        if not all(math.isfinite(value) for value in returns):
            return unavailable('NONFINITE_RETURN')
        try:
            mean = statistics.mean(returns)
            deviation = statistics.stdev(returns)
            downside = math.hypot(*(min(value, 0.0) for value in returns)) / math.sqrt(len(returns))
            sharpe = mean / deviation * math.sqrt(365) if deviation else None
            sortino = mean / downside * math.sqrt(365) if downside else None
            ratios.update(sharpe=sharpe if sharpe is not None and math.isfinite(sharpe) else None,
                          sortino=sortino if sortino is not None and math.isfinite(sortino) else None,
                          reason='AVAILABLE' if deviation and downside else 'ZERO_RISK_DENOMINATOR')
        except (OverflowError, ValueError):
            return unavailable('NONFINITE_RETURN')
    count = len(trades)
    result.update(available=True, status='AVAILABLE', realized_pnl=cumulative,
                  closed_pieces=count, last_close_ts=trades[-1]['exit_ts'] if trades else None,
                  trades=trades[-trade_limit:], equity_curve=_sample(curve, max_points),
                  daily_activity=_sample(days, max_points),
                  historical={'predictive': False, 'basis': 'Descriptive persisted closure pieces, not projected profit potential',
                              'win_rate': sum(p > 0 for p in profits) / count if count else None,
                              'mean_closure_pnl': cumulative / count if count else None,
                              'max_realized_drawdown': max_drawdown if count else None,
                              'best_closure_pnl': max(profits) if profits else None,
                              'worst_closure_pnl': min(profits) if profits else None})
    result['display'].update(trades_truncated=count > trade_limit,
                             equity_sampled=len(curve) > max_points,
                             daily_sampled=len(days) > max_points)
    return result
