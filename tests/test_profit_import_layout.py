"""Format/date-scope validation must agree in preview and ingestion."""
import os
import tempfile
import unittest
from pathlib import Path
from datetime import date,datetime,timedelta
from unittest.mock import patch
import pandas as pd
from openpyxl import Workbook
from sqlalchemy import select,func
from app import profit as J,processor as P,admin_ops as A
from app.db import get_engine,imports,profit_lines

class ProfitLayoutTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.engine=get_engine('sqlite:///'+str(self.root/'test.db'))
        self.env=patch.dict(os.environ,REPORT_STORAGE_MODE='replace');self.env.start()
    def tearDown(self):
        self.env.stop();self.engine.dispose();self.tmp.cleanup()
    def workbook(self,name='summary.xlsx',summary=True,basis='Job Date',bill=datetime(2026,1,3),title_range='From 01-Jan-2026 to 31-Dec-2026',unicode_spaces=False):
        wb=Workbook();ws=wb.active
        label='Job Profit Analysis Report' if summary else 'Charge wise Detail'
        if unicode_spaces:label=label.replace(' ','\u00a0')
        ws.append(['New Globe Logistik LLP\n'+label+' '+title_range]);ws.append(['Basis : '+basis])
        if summary:
            ws.append(['Location','LOB','Job No.','Job Date','Organization','Income (INR)','Expense (INR)'])
            ws.append(['Mumbai','FFWD AIR EXP','J1',datetime(2026,1,2),'Customer',100,50])
        else:
            ws.append(['Location','LOB','Job No.','Job Date','Organization','Charge','Date','Income (INR)','Expense (INR)'])
            ws.append(['Mumbai','FFWD AIR EXP','J1',datetime(2026,1,2),'Customer','Freight',bill,100,50])
            ws.append(['Total','','','','','','',100,50])
        path=self.root/name;wb.save(path);return str(path)
    def count(self,table):
        with self.engine.connect() as c:return c.execute(select(func.count()).select_from(table)).scalar()
    def test_summary_preview_is_explicit_and_read_only(self):
        path=self.workbook()
        self.assertEqual(J.profit_layout(path),'job_summary')
        preview=A.preview_any(self.engine,path)
        self.assertEqual(preview['verdict'],'rejected')
        self.assertIn('job-level profit summary',preview['message'])
        self.assertIn('Billing Date',preview['message'])
        self.assertEqual(self.count(imports),0)
    def test_summary_import_cannot_replace_finance_even_with_approval(self):
        detail=self.workbook(name='detail.xlsx',summary=False,basis='Billing Date')
        self.assertEqual(P.ingest_file(self.engine,detail,datetime(2026,11,7))['status'],'promoted')
        summary=self.workbook()
        result=P.ingest_file(self.engine,summary,datetime(2026,11,8),source_ref='audit-message',approve_review=True)
        self.assertEqual(result['status'],'failed');self.assertEqual(self.count(profit_lines),1)
        with self.engine.connect() as c:
            row=c.execute(select(imports).where(imports.c.id==result['import_id'])).mappings().one()
        self.assertEqual((row['report_type'],row['source_ref']),('JP','audit-message'))
    def test_preview_and_import_hold_job_date_charge_detail(self):
        path=self.workbook(summary=False,basis='Job Date')
        preview=A.preview_any(self.engine,path);result=P.ingest_file(self.engine,path,datetime(2026,11,7))
        self.assertEqual((preview['verdict'],result['status']),('needs_review','needs_review'))
        self.assertEqual(preview['message'],result['message']);self.assertEqual(self.count(profit_lines),0)
    def test_preview_and_import_hold_missing_or_out_of_range_billing_dates(self):
        for index,bill in enumerate([None,datetime(2025,12,31),datetime(2027,1,1)]):
            path=self.workbook(name=f'detail-{index}.xlsx',summary=False,basis='Billing Date',bill=bill)
            preview=A.preview_any(self.engine,path);result=P.ingest_file(self.engine,path,datetime(2026,11,7))
            self.assertEqual((preview['verdict'],result['status']),('needs_review','needs_review'))
            self.assertEqual(preview['message'],result['message'])
        self.assertEqual(self.count(profit_lines),0)
    def test_unicode_space_detail_title_and_valid_preview_still_work(self):
        path=self.workbook(summary=False,basis='Billing Date',unicode_spaces=True)
        self.assertTrue(J.is_profit_report(path));self.assertEqual(A.preview_any(self.engine,path)['verdict'],'ready')
        self.assertEqual(P.ingest_file(self.engine,path,datetime(2026,11,7))['status'],'promoted')
    def test_billing_timestamp_on_last_day_is_in_scope(self):
        path=self.workbook(summary=False,basis='Billing Date',bill=datetime(2026,12,31,23,59,59))
        self.assertEqual(A.preview_any(self.engine,path)['verdict'],'ready')
        self.assertEqual(P.ingest_file(self.engine,path,datetime(2027,1,2))['status'],'promoted')
    def test_register_is_not_misclassified(self):
        wb=Workbook();ws=wb.active;ws.append(['New Globe Logistik LLP']);ws.append(['Shipment Register(Air Export)'])
        ws.append(['Shipment No','Shipment Date','Branch','Customer','Status','Job Owner']);ws.append(['J1',datetime(2026,1,1),'Mumbai','Customer','Open','Owner'])
        path=self.root/'register.xlsx';wb.save(path)
        self.assertIsNone(J.profit_layout(str(path)))
        self.assertEqual(A.preview_any(self.engine,str(path))['report_type'],'AE')
