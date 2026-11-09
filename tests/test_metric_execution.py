import unittest,io,copy
from openpyxl import load_workbook
from app import metric_execution as X,metric_definitions as M
class MetricExecutionTests(unittest.TestCase):
 def fixture(self):
  return dict(user={'finance':True},built_at='test',rep=[0,4],reps=[['NG','AE'],['NG','AI'],['NG','OE'],['NG','OI'],['NCS','AE']],no=['S1','S1'],date=[20000,20000],chg=[1.25,2.5],teus=[0,0],cbm=[1,2],cols={'p_job':{'d':['=unsafe'], 'pc':[0,0]},'p_lob':{'d':['FFWD AIR EXP'],'pc':[0,0]}},p=dict(co=[0,1],jd=[20000,20000],income=[100,50],expense=[40,70],meta=[]))
 def test_cross_company_identity_totals_and_variance(self):
  d=self.fixture();q=dict(metric='profit.jobs',indices=[0,1],previous_indices=[0]);r=X.execute(d,q,M);self.assertEqual(r['current']['value'],2);self.assertEqual(r['difference'],1)
  q['metric']='profit.gp';r=X.execute(d,q,M);self.assertEqual(r['current']['value'],40);self.assertEqual(r['previous']['value'],60)
  q['metric']='profit.margin';r=X.execute(d,q,M);self.assertAlmostEqual(r['current']['value'],40/150)
 def test_no_finance_and_invalid_selection(self):
  d=self.fixture();d['user']['finance']=False
  with self.assertRaises(PermissionError):X.execute(d,dict(metric='profit.gp',indices=[0]),M)
  for idx in [[2],[-1],[True],['0']]:
   with self.assertRaises(ValueError):X.execute(d,dict(metric='ops.shipments',indices=idx),M)
 def test_snapshot_mismatch_rejects_stale_export(self):
  with self.assertRaises(ValueError):X.execute(self.fixture(),dict(metric='profit.gp',indices=[0],snapshot='old'),M)
 def test_workbook_reconciles_and_neutralizes_formula_injection(self):
  r=X.execute(self.fixture(),dict(metric='profit.gp',indices=[0,1],previous_indices=[]),M);w=load_workbook(io.BytesIO(X.workbook(r)),data_only=False)
  self.assertEqual(len(w.sheetnames),6);ws=w['Contributing Records'];headers=[c.value for c in ws[1]];amount=headers.index('profit')+1
  self.assertEqual(sum(ws.cell(row=i,column=amount).value for i in [2,3]),40)
  self.assertTrue(ws.cell(row=2,column=headers.index('job')+1).value.startswith("'="))
  self.assertEqual(w['Reconciliation']['B5'].value,0)
 def test_expected_cost_benchmark_and_distinct_source_periods(self):
  d=self.fixture();d['p']['expense']=[40,0]
  r=X.execute(d,dict(metric='profit.expected_adjusted',indices=[1],previous_indices=[0]),M)
  self.assertEqual(r['current']['value'],30);self.assertEqual(r['records'][0]['expected_cost'],20)
  self.assertEqual(r['previous']['value'],60);self.assertEqual(len(r['benchmark_records']),1)
  self.assertIn('Benchmark Records',load_workbook(io.BytesIO(X.workbook(r))).sheetnames)
 def test_ops_does_not_include_money(self):
  r=X.execute(self.fixture(),dict(metric='ops.shipments',indices=[0,1]),M);self.assertEqual(r['current']['value'],2);self.assertNotIn('income',r['records'][0])
if __name__=='__main__':unittest.main()
