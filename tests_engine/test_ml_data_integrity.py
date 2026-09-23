"""CA: training data boundary and archive provenance regressions."""
import json
import zipfile
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from icarus_engine.events.calendar import event_features, load_event_csv, seed_events
from icarus_engine.trainers.catalog import extract_archive, identify
from icarus_engine.trainers.dataset import attach_labels, load_ohlc
from icarus_engine.trainers.run import train_file, write_report


def test_future_event_and_surprise_are_never_features():
    events = [{'ts': 1000, 'kind': 'cpi', 'scope': 'equity', 'surprise': 5}]
    assert event_features(999, events, 'NQ')['any_macro'] == 0
    assert event_features(999, events, 'NQ')['surprise_abs'] == 0
    assert event_features(1000, events, 'NQ')['surprise_abs'] == 5
    assert event_features(1000, events, 'BTC')['any_macro'] == 0
    assert event_features(1000 + 20*3600 + 1, events, 'NQ')['any_macro'] == 0


def test_fomc_winter_is_14_new_york():
    events = seed_events()
    assert events
    assert all(datetime.fromtimestamp(e['ts'], ZoneInfo('America/New_York')).hour == 14 for e in events)


def test_owner_event_timestamp_honors_timezone(tmp_path):
    p = tmp_path / 'events.csv'
    p.write_text('ts_or_date,name,kind,scope,surprise\n2026-01-15T08:30:00-05:00,CPI,cpi,all,0.1\n')
    row = load_event_csv(p)[0]
    assert row['ts'] == datetime.fromisoformat('2026-01-15T13:30:00+00:00').timestamp()


def test_strict_training_rejects_reorder_and_close_only(tmp_path):
    p = tmp_path / 'bad.csv'
    p.write_text('time,open,high,low,close\n' + '\n'.join(f'{1000-i},1,2,1,2' for i in range(10)))
    with pytest.raises(ValueError, match='reversed'):
        load_ohlc(p, strict=True, family='tick')
    p.write_text('time,close\n' + '\n'.join(f'{1000+i},2' for i in range(10)))
    with pytest.raises(ValueError, match='OHLC required'):
        load_ohlc(p, strict=True, family='clock_minutes')


def test_clock_duplicate_rejected_but_event_sequence_preserved(tmp_path):
    p = tmp_path / 'events.csv'
    p.write_text('time,open,high,low,close\n' + '\n'.join(f'{1000+i//2},1,2,1,2' for i in range(10)))
    with pytest.raises(ValueError, match='non-increasing'):
        load_ohlc(p, strict=True, family='clock_minutes')
    assert len(load_ohlc(p, strict=True, family='tick')) == 10


def test_label_indices_survive_flat_prices_and_sensor_asof():
    bars = [{'ts': 1000+i, 'open': v, 'high': v+1, 'low': v-1, 'close': v}
            for i,v in enumerate([2,2,3,2,4,3])]
    sensors = {'vix_z': [{'available_ts': 1003, 'value': 7}]}
    rows = attach_labels(bars, 'tick', events=[], asset='NQ', sensors=sensors)
    assert rows[0]['row_index'] == 1 and rows[0]['label_index'] == 2
    assert rows[0]['x']['vix_z'] is None
    assert next(r for r in rows if r['ts'] == 1003)['x']['vix_z'] == 7
    changed = [dict(b) for b in bars]
    changed[-1]['close'] = 9999
    assert rows[:-1] == attach_labels(changed, 'tick', events=[], asset='NQ', sensors=sensors)[:-1]


@pytest.mark.parametrize('token,family', [('30S','clock_seconds'),('1T','tick'),('10R','range'),('1D','clock_daily'),('1W','clock_weekly'),('60','clock_hours'),('61','clock_hours')])
def test_explicit_family_tokens_not_conflated(token, family):
    info = identify(f'CME_MINI_DL_NQ1!, {token}.csv', 'Full csv candles only.zip')
    assert info['family'] == family and info['interval'] == token
    assert identify('CME_MINI_DL_NQ1!, 1M.csv', 'Full csv candles only.zip')['status'] == 'unsupported'


def test_ambiguous_chart_and_wrong_instruments_not_execution():
    assert identify('CME_MINI_DL_NQ1!, 1 3.csv', 'Csv files for different chart types.zip')['status'] == 'ambiguous'
    for name in ('BATS_AAPL, 1.csv', 'CME_DL_MBT1!, 1.csv', 'COINBASE_ETHUSD, 1.csv', 'COINBASE_SOLUSD, 1.csv'):
        assert identify(name, 'Full csv candles only.zip')['status'] == 'not_execution'
    assert identify('CME_DL_BTC1!, 1.csv', 'Full csv candles only.zip')['asset'] == 'BTCF'
    assert identify('COINBASE_BTCUSD, 1.csv', 'Full csv candles only.zip')['asset'] == 'BTC'


def test_archive_path_escape_and_differing_existing_files(tmp_path):
    p = tmp_path / 'input.zip'
    with zipfile.ZipFile(p, 'w') as z:
        z.writestr('../escape.csv', 'bad')
    # Dot paths are ignored, never extracted outside the selected directory.
    assert extract_archive(p, tmp_path / 'out') == []
    assert not (tmp_path / 'escape.csv').exists()
    with zipfile.ZipFile(p, 'w') as z:
        z.writestr('valid/a.csv', 'first')
    rows = extract_archive(p, tmp_path / 'out')
    assert rows[0]['sha256']
    with zipfile.ZipFile(p, 'w') as z:
        z.writestr('valid/a.csv', 'second')
    with pytest.raises(ValueError, match='differing'):
        extract_archive(p, tmp_path / 'out')


def test_xgb_file_fit_retains_baseline_and_reloadable_artifact(tmp_path):
    from icarus_engine.trainers.xgb import validate_artifact
    from icarus_engine.trainers.run import file_hash
    from icarus_engine.trainers.verify import verify_cell
    from icarus_engine.events.calendar import load_events
    p = tmp_path / 'NQ.csv'
    px = 100.0
    lines = ['time,open,high,low,close']
    for i in range(500):
        nxt = px + (1 if i % 5 < 3 else -1)
        lines.append(f'{1700000000+i},{px},{max(px,nxt)},{min(px,nxt)},{nxt}')
        px = nxt
    p.write_text('\n'.join(lines))
    report = train_file(p, 'tick', asset='NQ', model='xgb', options={'num_boost_round': 12})
    assert report['baseline']['model']['w']
    report['provenance'] = {'sha256': file_hash(p), 'interval': '1T'}
    out = tmp_path / 'NQ_tick_xgb.json'
    write_report(report, out)
    baseline = tmp_path / 'NQ_tick.json'
    write_report({**report['baseline'], 'asset': 'NQ', 'family': 'tick',
                  'dataset_sha256': file_hash(p)}, baseline)
    restored = json.loads(out.read_text())
    assert validate_artifact(restored, asset='NQ', family='tick')
    cell = {'asset': 'NQ', 'family': 'tick', 'chart_type': 'tick',
            'interval': '1T', 'sha256': file_hash(p), 'path': str(p)}
    assert verify_cell(cell, out, baseline, load_events(tmp_path))['status'] == 'verified'
    p.write_text(p.read_text() + '\n1700000501,2,3,1,2')
    with pytest.raises(ValueError, match='provenance differs'):
        verify_cell(cell, out, baseline, load_events(tmp_path))
    assert restored['training_signature']
    assert not list(tmp_path.glob('*.tmp'))
