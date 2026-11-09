"""Current JPR diagnostics must exclude retained legacy charge history."""
import json
import unittest
from datetime import date, datetime

from fastapi.testclient import TestClient
from sqlalchemy import insert, select

from app import auth
from app.db import imports, profit_lines
from app.server import create_app
from scripts import test_daily_replacement as fixtures


class AdminFreshnessTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.ReplacementTests()
        self.fixture.setUp()
        self.fixture.load(self.fixture.register())
        self.fixture.load_profit(self.fixture.profit())
        self.app = create_app(self.fixture.engine, self.fixture.tmp.name + '/up')
        self.client = TestClient(self.app)

    def tearDown(self):
        self.app.state.store.stop = True
        self.app.state.store.wake.set()
        self.fixture.tearDown()

    def login(self, role):
        auth.create_user(self.fixture.engine, 'audit@example.test', role, 'Audit fixture',
                         companies=['NG'], lobs=['AE'], finance=True, password='Synthetic-pass123')
        self.assertEqual(self.client.post('/auth/login', json={
            'login': 'audit@example.test', 'password': 'Synthetic-pass123'}).status_code, 200)

    def test_current_job_counts_and_provenance_ignore_newer_legacy_report(self):
        self.login('admin')
        with self.fixture.engine.begin() as connection:
            accepted = connection.execute(select(imports.c.id, imports.c.file_name).where(
                imports.c.report_type == 'JP', imports.c.status == 'promoted')).first()
            expected = connection.execute(select(profit_lines.c.id).where(
                profit_lines.c.to_import.is_(None))).all()
            legacy = connection.execute(insert(imports).values(company='NG', report_type='JP',
                received_at=datetime(2026, 11, 9), report_time=datetime(2026, 11, 9),
                file_name='newer-legacy-charge-report.xlsx', status='promoted',
                range_from=date(2026, 1, 1), range_to=date(2026, 12, 31),
                columns=json.dumps(['Job Date', 'Charge']))).inserted_primary_key[0]
            connection.execute(insert(profit_lines), [
                dict(company='NG', from_import=legacy, to_import=None, key='legacy-row',
                     job_no='LEGACY', job_date=date(2026, 6, 1), lob='FFWD AIR EXP',
                     income=900, expense=100, profit=800, extra={'_format': 'charge_detail'}),
                dict(company='NG', from_import=accepted.id, to_import=legacy, key='ended-job',
                     job_no='ENDED', job_date=date(2026, 6, 1), lob='FFWD AIR EXP',
                     income=900, expense=100, profit=800, extra={'_format': 'job_summary_v1'}),
            ])
        response = self.client.get('/api/admin/data-freshness')
        self.assertEqual(response.status_code, 200, response.text)
        row = next(r for r in response.json()['rows'] if
                   (r['company'], r['report_type'], r['year']) == ('NG', 'JP', 2026))
        self.assertEqual(row['rows'], len(expected))
        self.assertEqual(row['file_name'], accepted.file_name)
        self.assertEqual(row['last_attempt_status'], 'promoted')

    def test_freshness_requires_admin_not_just_finance_access(self):
        self.assertEqual(self.client.get('/api/admin/data-freshness').status_code, 401)
        self.login('finance')
        self.assertEqual(self.client.get('/api/admin/data-freshness').status_code, 403)
