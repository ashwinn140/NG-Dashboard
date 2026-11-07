"""Synthetic integration checks: no production data, credentials or writes."""
import copy
import os
from pathlib import Path
import sys
import tempfile
import unittest
from datetime import date, datetime, timedelta
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pandas as pd
from sqlalchemy import func, insert, select
from app import config, dataset as D, processor as P, profit as J
from app.db import get_engine, shipments, profit_lines
from app.server import Store, save_file


class ReplacementTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.engine = get_engine('sqlite:///' + self.tmp.name + '/db.sqlite')
        self.mode = patch.dict(os.environ, REPORT_STORAGE_MODE='replace')
        self.mode.start()
        self.clock = datetime(2026, 11, 7)
        self.sequence = 0

    def tearDown(self):
        self.mode.stop()
        self.engine.dispose()
        self.tmp.cleanup()

    def register(self, year=2026, customers=('A', 'B'), branch='Mumbai'):
        return P.Register('NG', 'AE', pd.DataFrame([
            {'Shipment No': f'JOB-{i}', 'Shipment Date': pd.Timestamp(year, 1, i + 1),
             'Branch': branch, 'Customer': customer, 'Status': 'Open', 'Job Owner': 'Owner',
             'Airline': 'Carrier', 'Gross Weight': 100, 'Unused ERP column': 'retained in database'}
            for i, customer in enumerate(customers)]), 'Air Export',
            range_from=date(year, 1, 1), range_to=date(year, 12, 31), branches=[branch])

    def load(self, reg, sha=None, approve=False, when=None):
        self.sequence += 1
        return P.process_register(self.engine, reg, 'report.xlsx', sha or str(self.sequence),
                                  when or self.clock + timedelta(minutes=self.sequence), approve_review=approve)

    def rows(self, table=shipments):
        with self.engine.connect() as c:
            return list(c.execute(select(table)).mappings())

    def test_daily_changes_do_not_accumulate_versions(self):
        self.load(self.register(2025))
        self.load(self.register())
        for i in range(30):
            result = self.load(self.register(customers=(f'Updated {i}', 'B')))
            self.assertEqual(result['changed'], 1)
        rows = self.rows()
        self.assertEqual(len(rows), 4)
        self.assertTrue(all(r['to_import'] is None for r in rows))
        self.assertEqual([r['customer'] for r in rows if r['shipment_date'].year == 2025], ['A', 'B'])
        self.assertEqual([r['customer'] for r in rows if r['shipment_date'].year == 2026], ['Updated 29', 'B'])

    def test_incorrect_report_range_cannot_change_other_years(self):
        self.load(self.register(2025))
        report = self.register(2025, customers=('Wrong range', 'B'))
        report.range_from, report.range_to = date(2026, 1, 1), date(2026, 12, 31)
        before = self.rows()
        self.assertEqual(self.load(report)['status'], 'failed')
        self.assertEqual(self.rows(), before)

    def test_scope_drop_review_stale_and_duplicate(self):
        self.load(self.register(2025))
        other = self.register(branch='Delhi')
        other.df['Shipment No'] = ['DEL-0', 'DEL-1']
        self.load(other)
        original = self.load(self.register(), sha='same-file')
        before = self.rows()
        self.assertEqual(self.load(self.register(), sha='same-file')['status'], 'duplicate')
        self.assertEqual(self.load(self.register(), when=self.clock)['status'], 'stale')
        smaller = self.register(customers=('Updated',))
        self.assertEqual(self.load(smaller)['status'], 'needs_review')
        self.assertEqual(self.rows(), before)
        accepted = self.load(smaller, approve=True)
        self.assertEqual((accepted['changed'], accepted['ended']), (1, 1))
        rows = self.rows()
        self.assertEqual(len(rows), 5)
        self.assertEqual(sum(r['branch'] == 'Delhi' for r in rows), 2)
        self.assertEqual(sum(r['shipment_date'].year == 2025 for r in rows), 2)
        self.assertTrue(all(r['to_import'] is None for r in rows))

    def profit(self, year=2026):
        frame = pd.DataFrame([
            {'Location': 'Mumbai', 'LOB': 'AIR EXPORT', 'Job No.': f'{year}-JOB-{i}',
             'Job Date': pd.Timestamp(year, month, 1), 'Date': pd.Timestamp(year, month, 2),
             'Charge': 'Freight', 'Trans No.': f'{year}-INV-{i}', 'Customer': 'Customer',
             'Party': 'Vendor', 'Income (INR)': 100., 'Expense (INR)': 50.}
            for i, month in enumerate((1, 1, 6))])
        return J.ProfitReport('NG', frame, 'Profit', date(year, 1, 1), date(year, 12, 31),
                              'Billing Date', {}, list(frame.columns))

    def load_profit(self, report, approve=False):
        self.sequence += 1
        return J.process_profit(self.engine, report, 'profit.xlsx', str(self.sequence),
                                self.clock + timedelta(minutes=self.sequence), approve_review=approve)

    def test_profit_replacement_preserves_other_billing_dates(self):
        self.load_profit(self.profit(2025))
        self.load_profit(self.profit())
        daily = self.profit()
        daily.df = daily.df.iloc[:1].copy()
        daily.df.loc[0, 'Income (INR)'] = 125.
        daily.range_to = date(2026, 1, 31)
        self.assertEqual(self.load_profit(daily)['status'], 'needs_review')
        self.assertEqual(len(self.rows(profit_lines)), 6)
        result = self.load_profit(daily, approve=True)
        self.assertEqual((result['changed'], result['ended']), (1, 1))
        rows = self.rows(profit_lines)
        self.assertEqual(len(rows), 5)
        self.assertEqual(sum(r['trans_date'].year == 2025 for r in rows), 3)
        self.assertEqual(sum(r['trans_date'].month == 6 for r in rows), 2)
        self.assertEqual(next(r['income'] for r in rows if r['job_no'] == '2026-JOB-0'), 125.)
        daily.basis = 'Job Date'
        self.assertEqual(self.load_profit(daily, approve=True)['status'], 'needs_review')

    def test_default_mode_keeps_history_and_diffs(self):
        with patch.dict(os.environ, REPORT_STORAGE_MODE='versioned'):
            self.load(self.register())
            self.load(self.register(customers=('Changed', 'B')))
            self.assertEqual(len(self.rows()), 3)
            change = D._changes(self.engine, 'NG', 'AE')
            self.assertEqual(len(change['changed']), 1)
            self.assertEqual(change['changed'][0][1], [['Customer', 'A', 'Changed']])

    def test_projected_dataset_matches_original_and_access_restrictions(self):
        self.load(self.register(2025))
        self.load(self.register())
        self.load_profit(self.profit())
        projected = D.build_full(self.engine)
        def original_frame(engine, company, rt):
            with engine.connect() as c:
                rows = c.execute(select(shipments.c.extra).where(shipments.c.company == company,
                    shipments.c.report_type == rt, shipments.c.to_import.is_(None)).order_by(shipments.c.id)).all()
            return pd.DataFrame([dict(r.extra) for r in rows]) if rows else pd.DataFrame()
        with patch.object(D, '_open_frame', original_frame):
            original = D.build_full(self.engine)
        original.pop('built_at'); projected.pop('built_at')
        self.assertEqual(projected, original)
        projected['built_at'] = 'test'
        restricted = D.restrict(projected, {'companies': ['NG'], 'lobs': ['AE'], 'finance': False})
        self.assertEqual(restricted['storage_mode'], 'replace')
        self.assertEqual(restricted['p']['co'], [])
        self.assertEqual(restricted['changes'], {})
        self.assertEqual(self.rows()[0]['extra']['Unused ERP column'], 'retained in database')
        with self.assertRaises(P.ReportError):
            P.snapshot(self.engine, 'NG', 'AE', 1)

    def test_repeat_attachment_reuses_archive(self):
        store = Store(self.engine, self.tmp.name + '/uploads', start_worker=False)
        first = save_file(store, b'example workbook', 'report.xlsx')
        second = save_file(store, b'example workbook', 'report.xlsx')
        self.assertEqual(first, second)
        self.assertEqual(len(list(Path(store.upload_dir).rglob('*.xlsx'))), 1)
        different = save_file(store, b'changed workbook', 'report.xlsx')
        self.assertNotEqual(first[0], different[0])
        self.assertEqual(Path(first[0]).read_bytes(), b'example workbook')


if __name__ == '__main__':
    unittest.main(verbosity=2)
