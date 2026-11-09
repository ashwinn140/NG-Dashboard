import unittest,io
from fastapi.testclient import TestClient
from openpyxl import load_workbook
from scripts import test_daily_replacement as F
from app.server import create_app
from app import auth
class MetricAPITests(unittest.TestCase):
 def setUp(self):
  self.f=F.ReplacementTests();self.f.setUp();self.f.load(self.f.register());self.f.load_profit(self.f.profit());self.app=create_app(self.f.engine,self.f.tmp.name+'/up');self.c=TestClient(self.app)
 def tearDown(self):self.app.state.store.stop=True;self.app.state.store.wake.set();self.f.tearDown()
 def login(self,finance):
  auth.create_user(self.f.engine,'metric@example.test','finance' if finance else 'operations','Metric user',companies=['NG'],lobs=['AE'],finance=finance,password='Synthetic-pass123')
  self.assertEqual(self.c.post('/auth/login',json=dict(login='metric@example.test',password='Synthetic-pass123')).status_code,200);self.c.headers['X-CSRF-Token']=self.c.get('/api/me').json()['csrf']
 def test_authentication_csrf_and_finance_scope(self):
  q=dict(metric='profit.gp',indices=[0]);self.assertEqual(self.c.post('/api/metrics/evidence',json=q).status_code,401);self.login(False)
  self.assertEqual(self.c.post('/api/metrics/evidence',json=q).status_code,403)
  self.assertTrue(all(x['id'].startswith('ops.') for x in self.c.get('/api/metrics/definitions').json()['metrics']))
  r=self.c.post('/api/metrics/evidence',json=dict(metric='ops.shipments',indices=[0]));self.assertEqual(r.status_code,200);self.assertNotIn('income',r.json()['records'][0])
  self.c.headers.pop('X-CSRF-Token');self.assertEqual(self.c.post('/api/metrics/export',json=q).status_code,403)
 def test_financial_evidence_export_and_invalid_index(self):
  self.login(True);q=dict(metric='profit.gp',indices=[0,1,2],previous_indices=[])
  r=self.c.post('/api/metrics/evidence',json=q);self.assertEqual(r.status_code,200,r.text);v=r.json();self.assertEqual(v['current']['value'],150)
  self.assertEqual({x['company'] for x in v['records']},{'NG'});q['snapshot']=v['snapshot'];r=self.c.post('/api/metrics/export',json=q);self.assertEqual(r.status_code,200);self.assertEqual(load_workbook(io.BytesIO(r.content))['Reconciliation']['B3'].value,150)
  q['indices']=[999];self.assertEqual(self.c.post('/api/metrics/evidence',json=q).status_code,400)
if __name__=='__main__':unittest.main()
