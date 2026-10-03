"""Synthetic source-integrity regressions; never empirical market evidence."""
import contextlib
import csv
import hashlib
import importlib
import io
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from datetime import timezone
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo

from icarus_engine.cli import main as engine_main
from icarus_engine.feeds.bars import FileFeed, parse_ohlcv_csv, parse_timestamp
from icarus_engine.learning_fabric import LearningFabric
from icarus_engine.trainers.dataset import load_ohlc
from icarus_engine.trainers.integrity import canonical_ts, inspect_ohlc
from icarus_engine.trainers.run import train_file, train_xgb_file


HEADERS = ['time', 'open', 'high', 'low', 'close', 'volume']


def write_csv(path, headers=HEADERS, rows=None):
    rows = rows if rows is not None else [[1700000000 + i * 60, 10, 12, 9, 11, 0] for i in range(12)]
    with path.open('w', newline='', encoding='utf-8') as handle:
        writer = csv.writer(handle)
        writer.writerow(headers)
        writer.writerows(rows)
    return path


class SourceDataContractTests(unittest.TestCase):
    def test_epoch_units_match_between_feed_and_trainer(self):
        for raw in ['1700000000', '1700000000000', '1700000000000000', '1700000000000000000']:
            with self.subTest(raw=raw):
                self.assertEqual(canonical_ts(raw), 1700000000)
                self.assertEqual(parse_timestamp(raw, timezone.utc), 1700000000)
        self.assertEqual(canonical_ts('946684800000'), 946684800)
        self.assertEqual(parse_timestamp('946684800000', timezone.utc), 946684800)
        self.assertEqual(canonical_ts('631152000000'), 631152000)
        self.assertIsNone(parse_timestamp('631152000000', timezone.utc))

    def test_iso_and_numeric_bounds_are_consistent(self):
        for raw in ['0', '-1', '4102444800', '4102444800000', '2100-01-01T00:00:00Z',
                    '2200-01-01T00:00:00Z', '1969-12-31T23:59:59Z', '1e100', 'nan', 'inf']:
            with self.subTest(raw=raw):
                self.assertIsNone(canonical_ts(raw))
                self.assertIsNone(parse_timestamp(raw, timezone.utc))

    def test_timestamp_record_keeps_units_raw_value_and_timezone_basis(self):
        try:
            normalize = importlib.import_module('icarus_engine.evidence.timestamps').normalize_timestamp
        except ImportError:
            self.fail('shared timestamp evidence parser is missing')
        for raw, unit in [('1700000000.125', 'seconds'), ('1700000000125', 'milliseconds'),
                          ('1700000000125000', 'microseconds'), ('1700000000125000000', 'nanoseconds')]:
            with self.subTest(raw=raw):
                record = normalize(raw)
                self.assertEqual(record.raw_value, raw)
                self.assertEqual(record.epoch_seconds, 1700000000.125)
                self.assertEqual(record.epoch_seconds_exact, '1700000000.125')
                self.assertEqual(record.detected_unit, unit)
                self.assertEqual(record.timezone_basis, 'UTC_EPOCH')
                self.assertFalse(record.whole_second)
        offset = normalize('2023-11-14T23:13:20+01:00')
        self.assertEqual(offset.epoch_seconds, 1700000000)
        self.assertEqual(offset.timezone_basis, 'EXPLICIT_OFFSET')
        self.assertIsNone(normalize('2023-11-14 22:13:20'))
        declared = normalize('2023-11-14 22:13:20', naive_timezone=timezone.utc)
        self.assertEqual(declared.epoch_seconds, 1700000000)
        self.assertEqual(declared.timezone_basis, 'DECLARED:UTC')

    def test_dst_fold_and_gap_have_no_guessed_timestamp(self):
        ny = ZoneInfo('America/New_York')
        for raw in ['2026-03-08 02:30', '2026-11-01 01:30']:
            with self.subTest(raw=raw):
                self.assertIsNone(parse_timestamp(raw, ny))
        self.assertEqual(parse_timestamp('2026-09-14 09:30', ny), 1789392600)
        self.assertIsNone(canonical_ts('2026-09-14 09:30'))

    def test_exact_iso_subseconds_cannot_masquerade_as_whole_seconds(self):
        normalize = importlib.import_module('icarus_engine.evidence.timestamps').normalize_timestamp
        for stamp, exact in [('2023-11-14T22:13:20.000000001Z', '1700000000.000000001'),
                             ('2023-11-14T22:13:20.125000000Z', '1700000000.125')]:
            with self.subTest(stamp=stamp):
                record = normalize(stamp)
                self.assertEqual(record.epoch_seconds_exact, exact)
                self.assertFalse(record.whole_second)
                with self.assertRaisesRegex(ValueError, 'subsecond'):
                    parse_ohlcv_csv(','.join(HEADERS) + '\n' + stamp + ',10,12,9,11,0\n')
        for stamp in ['2023-11-14T22:13:20+00:00:00.000000001', '2023-11-14T22:13:20+00:00:00.000001',
                      '20231114T221320+000000.000001', '2023-11-14T22:13+00:00:00.000001']:
            with self.subTest(offset_stamp=stamp):
                self.assertIsNone(normalize(stamp))
        with tempfile.TemporaryDirectory() as temp:
            path = write_csv(Path(temp)/'source.csv', rows=[
                ['2023-11-14T22:13:20.000000001Z', 10, 12, 9, 11, 0],
                ['2023-11-14T22:13:20.000000002Z', 10, 12, 9, 11, 0],
                ['2023-11-14T22:14:20Z', 10, 12, 9, 11, 0]])
            self.assertEqual(inspect_ohlc(path)[1]['status'], 'blocked')
            self.assertIn('precision', inspect_ohlc(path)[1]['reason'])

    def test_unrepresentable_wall_times_are_rejected_without_overflow(self):
        try:
            result = parse_timestamp('0001-01-01 00:00', ZoneInfo('Asia/Tokyo'))
        except OverflowError:
            self.fail('out-of-bounds wall time crashed normalization')
        self.assertIsNone(result)

    def test_integer_helper_floors_exact_seconds_without_float_rounding(self):
        self.assertEqual(parse_timestamp('1700000000.999999999', timezone.utc), 1700000000)
        self.assertEqual(parse_timestamp('4102444799.999999999', timezone.utc), 4102444799)
        self.assertIsNone(parse_timestamp('946684799.999999999', timezone.utc))

    def test_close_only_and_incomplete_ohlc_cannot_enter_trainers(self):
        cases = [(['time', 'close'], [[1700000000 + i * 60, 11] for i in range(12)]),
                 (HEADERS, [[1700000000 + i * 60, '', 12, 9, 11, 0] for i in range(12)]),
                 (HEADERS, [[1700000000 + i * 60, 10, 12, 9, 'nan', 0] for i in range(12)])]
        for headers, rows in cases:
            with self.subTest(headers=headers, row=rows[0]), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                path = write_csv(root / 'source.csv', headers, rows)
                bars, manifest = inspect_ohlc(path)
                self.assertEqual(manifest['status'], 'blocked')
                self.assertEqual(bars, [])
                with self.assertRaisesRegex(ValueError, 'OHLC'):
                    load_ohlc(path)
                for result in [train_file(path, '1m', asset='NQ'),
                               train_xgb_file(path, '1m', asset='NQ', out=root/'x.json', ledger=root/'l.sqlite3')]:
                    self.assertEqual(result['status'], 'blocked')
                    self.assertFalse(result['execution_authorized'])
                self.assertFalse((root / 'x.json').exists())

    def test_selected_duplicate_columns_are_ambiguous(self):
        for headers, row in [(HEADERS + ['Close'], [1700000000, 10, 12, 9, 11, 0, 11]),
                             (HEADERS + ['TIDE Long', 'TIDE Long'], [1700000000, 10, 12, 9, 11, 0, 1, 2])]:
            with self.subTest(headers=headers), tempfile.TemporaryDirectory() as temp:
                path = write_csv(Path(temp) / 'source.csv', headers, [row])
                self.assertEqual(inspect_ohlc(path)[1]['status'], 'blocked')
        with self.assertRaisesRegex(ValueError, 'ambiguous'):
            parse_ohlcv_csv('time,open,high,low,close,Close\n1700000000,10,12,9,11,11\n')
        self.assertEqual(len(parse_ohlcv_csv('time,open,high,low,close,Overlay,Overlay\n1700000000,10,12,9,11,1,2\n')), 1)

    def test_feed_conflicts_are_rejected_in_each_source_order(self):
        rows = ['1700000000,10,12,9,11,0', '1700000000,10,13,9,12,0']
        for order in [rows, rows[::-1]]:
            with self.subTest(order=order), self.assertRaisesRegex(ValueError, 'conflict'):
                parse_ohlcv_csv(','.join(HEADERS) + '\n' + '\n'.join(order) + '\n')
        exact = ','.join(HEADERS) + '\n' + rows[0] + '\n' + rows[0] + '\n'
        self.assertEqual(len(parse_ohlcv_csv(exact)), 1)
        self.assertEqual(parse_ohlcv_csv(exact)[0].v, 0)

    def test_feed_refuses_impossible_or_nonfinite_ohlc_and_volume(self):
        for fields in ['10,9,8,11,0', '10,12,11,11,0', '10,12,9,nan,0', '10,12,9,11,inf', '10,12,9,11,-1']:
            with self.subTest(fields=fields), self.assertRaisesRegex(ValueError, 'OHLC|volume'):
                parse_ohlcv_csv(','.join(HEADERS) + '\n1700000000,' + fields + '\n')

    def test_integer_bar_feed_does_not_collapse_subsecond_clocks(self):
        for stamp in ['1700000000.125', '1700000000125', '1700000000125000', '1700000000125000000']:
            with self.subTest(stamp=stamp), self.assertRaisesRegex(ValueError, 'subsecond'):
                parse_ohlcv_csv(','.join(HEADERS) + '\n' + stamp + ',10,12,9,11,0\n')
        with tempfile.TemporaryDirectory() as temp:
            path = write_csv(Path(temp)/'source.csv', rows=[
                ['1700000000000000001', 10, 12, 9, 11, 0],
                ['1700000000000000002', 10, 12, 9, 11, 0],
                ['1700000060000000000', 10, 12, 9, 11, 0]])
            self.assertEqual(inspect_ohlc(path)[1]['status'], 'blocked')
            self.assertIn('precision', inspect_ohlc(path)[1]['reason'])

    def test_file_reload_preserves_declared_timezone_and_old_rows_on_failure(self):
        with tempfile.TemporaryDirectory() as temp:
            path = write_csv(Path(temp)/'source.csv', rows=[['2023-11-14 22:13:20', 10, 12, 9, 11, 0]])
            feed = FileFeed.from_csv(str(path), tz=timezone.utc)
            self.assertEqual(feed._bars[0].ts, 1700000000)
            write_csv(path, rows=[['2023-11-14 22:13:20', 10, 12, 9, 11, 0],
                                  ['2023-11-14 22:14:20', 11, 13, 10, 12, 0]])
            os.utime(path, (feed._mtime + 2, feed._mtime + 2))
            self.assertEqual(feed.ticker('NQ'), 12)
            self.assertEqual([bar.ts for bar in feed._bars], [1700000000, 1700000060])
            write_csv(path, rows=[[1700000000, 10, 12, 9, 11, 0], [1700000000, 10, 13, 9, 12, 0]])
            os.utime(path, (feed._mtime + 2, feed._mtime + 2))
            with self.assertRaisesRegex(ValueError, 'conflict'):
                feed.ticker('NQ')
            self.assertEqual([bar.ts for bar in feed._bars], [1700000000, 1700000060])

    def test_rejected_cli_source_does_not_overwrite_history(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            dest = write_csv(root/'history.csv')
            before = dest.read_bytes()
            source = write_csv(root/'bad.csv', rows=[[1700000000, 10, 12, 9, 11, 0],
                                                    [1700000000, 10, 13, 9, 12, 0]])
            stderr = io.StringIO()
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(stderr):
                code = engine_main(['ingest-bars', str(source), '--symbol', 'NQ', '--out', str(dest)])
            self.assertEqual(code, 2)
            self.assertIn('conflict', stderr.getvalue())
            self.assertEqual(dest.read_bytes(), before)

    def test_catalogue_hash_and_manifest_use_one_byte_snapshot(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            path = write_csv(root/'source.csv')
            original = path.read_bytes()
            def replace_before_parse(source, **kwargs):
                write_csv(path, rows=[[1700000000+i*60, 20, 22, 19, 21, 0] for i in range(12)])
                return inspect_ohlc(source, **kwargs)
            fabric = LearningFabric(root)
            try:
                with patch('icarus_engine.learning_fabric.inspect_ohlc', side_effect=replace_before_parse):
                    result = fabric.register_dataset(path, asset='NQ', chart_type='1m')['dataset']
                expected = hashlib.sha256(original).hexdigest()
                self.assertEqual(result['raw_sha256'], expected)
                self.assertEqual(result['manifest']['raw_sha256'], expected)
            finally:
                fabric._conn.close()

    def test_old_parse_metadata_is_refreshed_and_old_training_receipt_preserved(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            path = write_csv(root/'source.csv', ['time', 'close'], [[1700000000+i*60, 11] for i in range(12)])
            fabric = LearningFabric(root)
            try:
                dataset = fabric.register_dataset(path, asset='NQ', chart_type='1m')['dataset']
                old_manifest = dict(dataset['manifest'], parser='icarus.trainer.integrity/1', status='clean', reason='')
                report_raw = json.dumps({'status':'fitted', 'dataset_manifest':old_manifest, 'execution_authorized':False})
                with fabric._conn:
                    fabric._conn.execute('UPDATE datasets SET manifest_json=? WHERE dataset_id=?', (json.dumps(old_manifest), dataset['dataset_id']))
                    fabric._conn.execute('INSERT INTO training_runs VALUES(?,?,?,?,?,?)', ('legacy-run', dataset['dataset_id'], 'logit', report_raw, 'fitted', '2026-09-30T00:00:00Z'))
                refreshed = fabric.register_dataset(path, asset='NQ', chart_type='1m')['dataset']
                self.assertEqual(refreshed['manifest']['status'], 'blocked')
                self.assertEqual(refreshed['manifest']['parser'], 'icarus.trainer.integrity/2')
                result = fabric.backfill_dataset(dataset['dataset_id'], slots=['logit'])
                self.assertEqual(result['status'], 'needs_requalification')
                self.assertEqual(fabric.training_runs()[0]['status'], 'needs_requalification')
                self.assertEqual(fabric._conn.execute('SELECT report_json FROM training_runs').fetchone()[0], report_raw)
                self.assertEqual(len(fabric.training_runs()), 1)
                fabric._config['auto_train_slots'] = ['logit', 'xgb']
                self.assertEqual(fabric._next_untrained(4), [])
                self.assertEqual(fabric.health()['backlog']['ohlc_requalification_runs'], 1)
                self.assertEqual(fabric.snapshot()['training']['needs_requalification_count'], 1)
            finally:
                fabric._conn.close()

    def test_backfill_parses_the_verified_snapshot_after_path_replacement(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            path = write_csv(root/'source.csv')
            original_sha = hashlib.sha256(path.read_bytes()).hexdigest()
            fabric = LearningFabric(root)
            try:
                dataset = fabric.register_dataset(path, asset='NQ', chart_type='1m')['dataset']
                def replace_before_train(source, *args, **kwargs):
                    write_csv(path, rows=[[1700000000+i*60, 20, 19, 21, 22, 0] for i in range(12)])
                    return train_file(source, *args, **kwargs)
                with patch('icarus_engine.learning_fabric.train_file', side_effect=replace_before_train):
                    result = fabric.backfill_dataset(dataset['dataset_id'], slots=['logit'])
                self.assertEqual(result['runs'][0]['report']['dataset_manifest']['raw_sha256'], original_sha)
                self.assertEqual(result['runs'][0]['report']['status'], 'skipped')
            finally:
                fabric._conn.close()

    def test_reinspection_preserves_original_intake_declarations(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            path = write_csv(root/'source.csv')
            fabric = LearningFabric(root)
            try:
                original = fabric.register_dataset(path, asset='NQ', chart_type='1m',
                                                   intake={'symbol':'NQ', 'timeframe':'1m'})['dataset']
                repeated = fabric.register_dataset(path, asset='ES', chart_type='5m',
                                                   intake={'symbol':'ES', 'timeframe':'5m'})['dataset']
                self.assertEqual(repeated['asset'], 'NQ')
                self.assertEqual(repeated['chart_type'], '1m')
                self.assertEqual(repeated['manifest']['intake'], original['manifest']['intake'])
            finally:
                fabric._conn.close()

    def test_parser_code_changes_change_both_protected_study_identities(self):
        from icarus_engine.trainers import artifact, rank_slot, xgb_slot
        source_root = Path(artifact.__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for name in {*xgb_slot.CODE_FILES, *rank_slot.CODE_FILES, 'evidence/timestamps.py', 'trainers/integrity.py'}:
                dest = root / name
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes((source_root/name).read_bytes())
            with patch.object(artifact, '__file__', str(root/'trainers/artifact.py')):
                xgb_before, rank_before = xgb_slot.study_sha256(), rank_slot.study_sha256()
                with (root/'evidence/timestamps.py').open('ab') as handle:
                    handle.write(b'\n# synthetic parser mutation\n')
                self.assertNotEqual(xgb_slot.study_sha256(), xgb_before)
                self.assertNotEqual(rank_slot.study_sha256(), rank_before)
                rank_before = rank_slot.study_sha256()
                with (root/'trainers/integrity.py').open('ab') as handle:
                    handle.write(b'\n# synthetic integrity mutation\n')
                self.assertNotEqual(rank_slot.study_sha256(), rank_before)

    @unittest.skipUnless(shutil.which('node'), 'Node executes the shipped Learning UI')
    def test_learning_ui_exposes_and_clears_old_ohlc_review(self):
        source = Path(__file__).resolve().parents[1] / 'icarus_engine/learning-ui.js'
        code = r'''
const fs = require('fs'), vm = require('vm'), assert = require('assert');
const panel = {innerHTML: ''};
let state = {training: {run_count: 1, needs_requalification_count: 1}};
const context = {window: {}, document: {querySelector: () => panel},
  localStorage: {getItem: () => 'synthetic-test-token'},
  fetch: async path => ({ok: true, json: async () => path === '/api/learning' ? state : {}})};
vm.runInNewContext(fs.readFileSync(process.argv[1], 'utf8'), context);
(async () => {
  await context.window.loadLearning();
  assert(panel.innerHTML.includes('OHLC training requires requalification: 1 prior receipts.'));
  state = {training: {run_count: 1, needs_requalification_count: 0}};
  await context.window.loadLearning();
  assert(!panel.innerHTML.includes('OHLC training requires requalification:'));
})().catch(error => {console.error(error); process.exitCode = 1;});
'''
        completed = subprocess.run(['node', '-e', code, str(source)], capture_output=True, text=True, timeout=15)
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)

    def test_changed_source_bytes_cannot_train_catalogued_identity(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            path = write_csv(root/'source.csv')
            fabric = LearningFabric(root)
            try:
                dataset = fabric.register_dataset(path, asset='NQ', chart_type='1m')['dataset']
                write_csv(path, rows=[[1700000000+i*60, 20, 22, 19, 21, 0] for i in range(12)])
                result = fabric.backfill_dataset(dataset['dataset_id'], slots=['logit'])
                self.assertEqual(result['status'], 'blocked')
                self.assertIn('bytes', result['reason'])
                self.assertEqual(fabric.training_runs(), [])
            finally:
                fabric._conn.close()

    def test_repeated_blocked_backfill_does_not_report_completion(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            path = write_csv(root/'source.csv', ['time', 'close'], [[1700000000+i*60, 11] for i in range(12)])
            fabric = LearningFabric(root)
            try:
                dataset = fabric.register_dataset(path, asset='NQ', chart_type='1m')['dataset']
                first = fabric.backfill_dataset(dataset['dataset_id'], slots=['logit'])
                again = fabric.backfill_dataset(dataset['dataset_id'], slots=['logit'])
                self.assertEqual(first['status'], 'blocked')
                self.assertEqual(again['status'], 'blocked')
                self.assertTrue(again['runs'][0]['idempotent'])
                self.assertEqual(first['runs'][0]['report'], again['runs'][0]['report'])
            finally:
                fabric._conn.close()


if __name__ == '__main__':
    unittest.main()
