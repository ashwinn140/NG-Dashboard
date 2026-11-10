"""Independent correctness and permission regressions using controlled ERP records."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from datetime import date
from unittest.mock import patch
import pandas as pd
from sqlalchemy import select, func
from scripts.test_daily_replacement import ReplacementTests
from app import dataset as D
from app.db import profit_lines

class DashboardAuditTests(unittest.TestCase):
    def setUp(self):
        self.fixture = ReplacementTests(); self.fixture.setUp()
    def tearDown(self):
        self.fixture.tearDown()
    def test_ambiguous_shipment_number_never_uses_first_row(self):
        f=self.fixture
        f.load(f.register(2025)); f.load(f.register(2026))
        p=f.profit(); p.df=p.df.iloc[:1].copy(); p.df['Job No.']='JOB-0'; p.df['Job Date']=pd.Timestamp(2026,3,1)
        f.load_profit(p)
        ds=D.build_full(f.engine)
        self.assertEqual(ds['p']['sidx'],[-1])
        self.assertEqual(sum(ds['p']['income']),100)
        self.assertEqual(sum(ds['p']['expense']),50)
    def test_unique_exact_match_and_lob_prevent_wrong_attribution(self):
        f=self.fixture
        f.load(f.register(2025)); f.load(f.register(2026))
        p=f.profit(); p.df=p.df.iloc[:1].copy(); p.df['Job No.']='JOB-0'; p.df['Job Date']=pd.Timestamp(2026,1,1)
        f.load_profit(p); ds=D.build_full(f.engine)
        self.assertEqual(ds['date'][ds['p']['sidx'][0]],(date(2026,1,1)-date(1970,1,1)).days)
        p.df['LOB']='SEA IMPORT'; f.load_profit(p,approve=True); ds=D.build_full(f.engine)
        self.assertEqual(ds['p']['sidx'],[-1])
    def test_finance_totals_groupings_and_permissions(self):
        f=self.fixture; r=f.register(); r.df['Buy Rate (UDF)']=10; r.df['Sell Rate (UDF)']=20
        f.load(r); f.load_profit(f.profit()); ds=D.build_full(f.engine)
        self.assertEqual((sum(ds['p']['income']),sum(ds['p']['expense'])),(300,150))
        for co in ['NG','NCS']:
            for lob in ['AE','AI','OE','OI']:
                scoped=D.restrict(ds,dict(companies=[co],lobs=[lob],finance=True))
                self.assertTrue(all(ds['reps'][i]==[co,lob] for i in scoped['rep']))
                self.assertTrue(all(i==['AE','AI','OE','OI'].index(lob) for i in scoped['p']['rt']))
        scoped=D.restrict(ds,dict(companies=['NG'],lobs=['AE'],finance=False))
        self.assertEqual(scoped['p']['income'],[])
        self.assertTrue(all(x==0 for k in ['rbuy','rsell','rbf','rsf'] for x in scoped[k]))
    def test_source_precision_is_preserved_until_display(self):
        f=self.fixture; r=f.register()
        r.df['Chargeable Wt']=[1234.56,2.34]; r.df['Gross Weight']=[999.99,1.23]
        r.df['Volume']=[0.123,1.987]; f.load(r); ds=D.build_full(f.engine)
        self.assertAlmostEqual(sum(ds['chg'])*1000,1236.90)
        self.assertAlmostEqual(sum(ds['gross'])*1000,1001.22)
        self.assertAlmostEqual(sum(ds['cbm']),2.110)
        self.assertEqual(ds['ckg'],[1234.56,2.34])

    def test_removed_feature_and_authentication_routes(self):
        from fastapi.testclient import TestClient
        from app.server import create_app
        from app import auth
        from app.db import users
        f=self.fixture
        app=create_app(f.engine, f.tmp.name+'/uploads')
        try:
            client=TestClient(app)
            self.assertEqual(client.get('/phase2/intelligence').status_code,401)
            self.assertEqual(client.get('/api/dataset').status_code,401)
            uid=auth.create_user(f.engine,'audit@example.test','admin','Audit',password='Synthetic-pass123')
            self.assertEqual(client.post('/auth/login',json={'login':'audit@example.test','password':'Synthetic-pass123'}).status_code,200)
            self.assertEqual(client.get('/phase2/intelligence').status_code,410)
            self.assertNotIn('Business Intelligence <span',client.get('/').text)
        finally:
            app.state.store.stop=True; app.state.store.wake.set()


    def test_production_image_builds_dashboard_from_canonical_frontend(self):
        root=Path(__file__).resolve().parents[1]
        dockerfile=(root/'Dockerfile').read_text()
        self.assertIn('COPY frontend ./frontend',dockerfile)
        self.assertIn('RUN sh frontend/build.sh',dockerfile)
        self.assertLess(dockerfile.index('COPY app ./app'),dockerfile.index('COPY frontend ./frontend'))
        self.assertLess(dockerfile.index('COPY frontend ./frontend'),dockerfile.index('RUN sh frontend/build.sh'))
        self.assertLess(dockerfile.index('RUN sh frontend/build.sh'),dockerfile.index('COPY entrypoint.sh /entrypoint.sh'))

    def test_production_build_reproduces_served_asset(self):
        root=Path(__file__).resolve().parents[1]
        page=(root/'frontend/production_shell.html').read_text()
        for token,path in {'__PRODUCTION_FFLATE__':'vendor/fflate.js','__PRODUCTION_D3__':'vendor/d3.min.js','__PRODUCTION_APP__':'app_prod.js'}.items():
            self.assertEqual(page.count(token),1)
            page=page.replace(token,(root/'frontend'/path).read_text(),1)
        self.assertEqual(page,(root/'app/web/dashboard.html').read_text())

    def test_empty_register_finance_restriction_does_not_crash(self):
        f=self.fixture; f.load(f.register()); f.load_profit(f.profit());ds=D.build_full(f.engine)
        for k in ['rep','no','date','ops','fin','gross','chg','teus','cbm','ckg','rbuy','rbf','rsell','rsf','inv1','invN']:ds[k]=[]
        ds['p']['sidx']=[-1]*len(ds['p']['co'])
        for c in ds['cols'].values():
            if 'c' in c:c['c']=[]
        self.assertEqual(D.restrict(ds,dict(companies=[],lobs=[],finance=True))['p']['sidx'],[-1]*3)

if __name__=='__main__': unittest.main()
