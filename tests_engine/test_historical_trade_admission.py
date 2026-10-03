"""Synthetic closure oracles; no owner exports or financial qualification."""
import csv
import hashlib
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from openpyxl import Workbook

from icarus_engine.learning_fabric import LearningFabric
from icarus_engine.parity import read_tv_trades


HEADERS = ['Trade number', 'Type', 'Date and time', 'Signal', 'Price USD', 'Size (qty)', 'Net PnL USD']


def trade_rows(entry_qty=1, exit_qty=1):
    # TradingView puts the exit before the entry in real exports.
    return [[1, 'Exit long', '2024-01-02 11:00', 'close', 101, exit_qty, 10],
            [1, 'Entry long', '2024-01-02 10:00', 'entry', 100, entry_qty, 10]]


def write_source(path, rows):
    if path.suffix == '.csv':
        with path.open('w', newline='', encoding='utf-8') as handle:
            writer = csv.writer(handle)
            writer.writerow(HEADERS)
            writer.writerows(rows)
    else:
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = 'Trades'
        sheet.append(HEADERS)
        for row in rows:
            sheet.append(row)
        workbook.save(path)
        workbook.close()
    return hashlib.sha256(path.read_bytes()).hexdigest()


class HistoricalTradeAdmissionTests(unittest.TestCase):
    def test_partial_overclosed_and_nonpositive_pieces_cannot_be_completed(self):
        cases = [trade_rows(2, 1), trade_rows(1, 2), trade_rows(1, -1),
                 trade_rows(1e-12, 2e-12), trade_rows(1e12, 1e12 - 1),
                 trade_rows(1, 0), trade_rows(1, 2) + [[1, 'Exit long', '2024-01-02 11:10', 'close2', 102, -1, -2]]]
        for suffix in ['.csv', '.xlsx']:
            for rows in cases:
                with self.subTest(suffix=suffix, rows=rows), tempfile.TemporaryDirectory() as temp:
                    base = Path(temp)
                    path = base / ('synthetic' + suffix)
                    write_source(path, rows)
                    fabric = LearningFabric(base)
                    try:
                        registered = fabric.register_dataset(path, asset='NQ', chart_type='20m', intake={'artifact_class': 'strategy_report_xlsx'} if suffix == '.xlsx' else None)
                        dataset = registered['dataset']
                        self.assertIsNone(fabric._historical_trade_signature(dataset))
                        result = fabric.backfill_dataset(dataset['dataset_id'])
                        self.assertEqual(fabric.experience_state()['count'], 0)
                        self.assertTrue(result['runs'][0]['report']['errors'])
                    finally:
                        fabric._conn.close()

    def test_invalid_row_relationships_have_durable_diagnostics(self):
        cases = []
        wrong_exit = trade_rows(); wrong_exit[0][1] = 'Exit short'; cases.append(wrong_exit)
        unknown_entry = trade_rows(); unknown_entry[1][1] = 'Entry garbage'; cases.append(unknown_entry)
        orphan = trade_rows() + [[9, 'Exit long', '2024-01-02 12:00', 'orphan', 103, 1, 3]]; cases.append(orphan)
        early = trade_rows(); early[0][2] = '2024-01-02 09:00'; cases.append(early)
        duplicate_entry = trade_rows() + [trade_rows()[1]]; cases.append(duplicate_entry)
        for suffix in ['.csv', '.xlsx']:
            for rows in cases:
                with self.subTest(suffix=suffix, rows=rows), tempfile.TemporaryDirectory() as temp:
                    base = Path(temp); path = base / ('synthetic' + suffix)
                    write_source(path, rows); fabric = LearningFabric(base)
                    try:
                        dataset = fabric.register_dataset(path, asset='NQ', chart_type='20m', intake={'artifact_class': 'strategy_report_xlsx'} if suffix == '.xlsx' else None)['dataset']
                        self.assertIsNone(fabric._historical_trade_signature(dataset))
                        result = fabric.backfill_dataset(dataset['dataset_id'])
                        self.assertEqual(fabric.experience_state()['count'], 0)
                        self.assertTrue(result['runs'][0]['report']['errors'])
                        repeated = fabric.backfill_dataset(dataset['dataset_id'])
                        self.assertTrue(repeated['runs'][0]['idempotent'])
                        self.assertEqual(repeated['status'], result['status'])
                    finally:
                        fabric._conn.close()

    def test_open_tail_does_not_double_count_completed_csv_xlsx_twins(self):
        rows = trade_rows() + [[2, 'Exit long', 'Open', 'Open', '', 1, 0],
                               [2, 'Entry long', '2024-01-02 12:00', 'entry', 102, 1, 0]]
        for first in ['trade_list', 'strategy_report_xlsx']:
            with self.subTest(first=first), tempfile.TemporaryDirectory() as temp:
                base = Path(temp); history = base / 'history'; history.mkdir()
                csv_path = history / 'synthetic.csv'; xlsx_path = history / 'synthetic.xlsx'
                csv_sha = write_source(csv_path, rows); xlsx_sha = write_source(xlsx_path, rows)
                fields = ['sha256', 'canonical_filename', 'format', 'artifact_class', 'symbol', 'timeframe', 'chart_type', 'rows', 'last_trade_number']
                with (history / 'EXPORT_INTAKE_MANIFEST.csv').open('w', newline='') as handle:
                    writer = csv.DictWriter(handle, fieldnames=fields); writer.writeheader()
                    common = {'symbol': 'CME_MINI:NQ1!', 'rows': 4, 'last_trade_number': 2}
                    writer.writerow({**common, 'sha256': csv_sha, 'canonical_filename': csv_path.name, 'format': 'csv', 'artifact_class': 'trade_list'})
                    writer.writerow({**common, 'sha256': xlsx_sha, 'canonical_filename': xlsx_path.name, 'format': 'xlsx', 'artifact_class': 'strategy_report_xlsx', 'timeframe': '20 minutes', 'chart_type': 'Candles'})
                fabric = LearningFabric(base)
                try:
                    fabric.scan_history(); datasets = {row['artifact_class']: row for row in fabric.datasets()}
                    signatures = {fabric._historical_trade_signature(row) for row in datasets.values()}
                    self.assertNotIn(None, signatures); self.assertEqual(len(signatures), 1)
                    second = 'strategy_report_xlsx' if first == 'trade_list' else 'trade_list'
                    fabric.backfill_dataset(datasets[first]['dataset_id'])
                    result = fabric.backfill_dataset(datasets[second]['dataset_id'])
                    self.assertTrue(result['runs'][0]['report']['deduplicated_by_strategy_report'])
                    state = fabric.experience_state()
                    self.assertEqual(state['count'], 1); self.assertEqual(state['closure_scoped_count'], 0)
                finally:
                    fabric._conn.close()

    def test_fractional_partial_exits_and_grouped_entry_numbers_remain_valid(self):
        cases = [trade_rows(0.3, 0.1) + [[1, 'Exit long', '2024-01-02 11:10', 'close2', 102, 0.2, 2]],
                 trade_rows(0.1, 0.1) + [[2, 'Exit long', '2024-01-02 11:10', 'close2', 102, 0.2, 2], [2, 'Entry long', '2024-01-02 10:00', 'entry', 100, 0.2, 2]]]
        for suffix in ['.csv', '.xlsx']:
            for rows in cases:
                with self.subTest(suffix=suffix), tempfile.TemporaryDirectory() as temp:
                    base = Path(temp); path = base / ('synthetic' + suffix)
                    write_source(path, rows); fabric = LearningFabric(base)
                    try:
                        dataset = fabric.register_dataset(path, asset='NQ', chart_type='20m', intake={'artifact_class': 'strategy_report_xlsx'} if suffix == '.xlsx' else None)['dataset']
                        self.assertIsNotNone(fabric._historical_trade_signature(dataset))
                        result = fabric.backfill_dataset(dataset['dataset_id'])
                        self.assertEqual(result['runs'][0]['report']['experience_count'], 1)
                        self.assertEqual(fabric.experience_state()['count'], 1)
                    finally:
                        fabric._conn.close()

    def test_legacy_parity_comparison_keeps_its_default_behavior(self):
        rows = trade_rows(); rows[1][1] = 'Entry garbage'
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'synthetic.csv'; write_source(path, rows)
            self.assertEqual(read_tv_trades(str(path))[0]['dir'], -1)

    def test_legacy_import_receipts_require_review_without_rewriting_evidence(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp); path = base / 'synthetic.csv'; write_source(path, trade_rows())
            fabric = LearningFabric(base)
            try:
                dataset = fabric.register_dataset(path, asset='NQ', chart_type='20m')['dataset']
                result = fabric.backfill_dataset(dataset['dataset_id'])
                report = dict(result['runs'][0]['report'])
                self.assertEqual(report.pop('historical_admission_version'), 2)
                legacy_json = json.dumps(report, sort_keys=True)
                with fabric._conn:
                    fabric._conn.execute('UPDATE training_runs SET report_json=?', (legacy_json,))
                repeated = fabric.backfill_dataset(dataset['dataset_id'])
                self.assertEqual(repeated['status'], 'needs_requalification')
                self.assertEqual(fabric.training_runs()[0]['status'], 'needs_requalification')
                self.assertEqual(fabric.experience_state()['legacy_historical_import_runs'], 1)
                self.assertEqual(fabric.experience_state()['count'], 1)
                self.assertEqual(fabric._conn.execute('SELECT report_json FROM training_runs').fetchone()[0], legacy_json)
            finally:
                fabric._conn.close()

    @unittest.skipUnless(shutil.which('node'), 'Node is required to execute the shipped Learning UI')
    def test_learning_ui_renders_and_clears_the_legacy_review_notice(self):
        source = Path(__file__).resolve().parents[1] / 'icarus_engine' / 'learning-ui.js'
        code = r'''
const fs = require('fs'), vm = require('vm'), assert = require('assert');
const panel = {innerHTML: ''};
let state = {experiences: {legacy_historical_import_runs: 2}};
const context = {window: {}, document: {querySelector: () => panel},
  localStorage: {getItem: () => 'synthetic-test-token'},
  fetch: async path => ({ok: true, json: async () => path === '/api/learning' ? state : {}})};
vm.runInNewContext(fs.readFileSync(process.argv[1], 'utf8'), context);
(async () => {
  await context.window.loadLearning();
  assert(panel.innerHTML.includes('Historical imports require requalification: 2 older receipts.'));
  state = {experiences: {legacy_historical_import_runs: 0}};
  await context.window.loadLearning();
  assert(!panel.innerHTML.includes('Historical imports require requalification:'));
})().catch(error => {console.error(error); process.exitCode = 1;});
'''
        completed = subprocess.run(['node', '-e', code, str(source)], capture_output=True, text=True, timeout=15)
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)


if __name__ == '__main__':
    unittest.main()
