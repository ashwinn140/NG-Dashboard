import unittest,io,copy
from openpyxl import load_workbook
from app import metric_execution as X,metric_definitions as M
class MetricExecutionTests(unittest.TestCase):
 def fixture(self):
  return dict(user={'finance':True},built_at='test',rep=[0,4],reps=[['NG','AE'],['NG','AI'],['NG','OE'],['NG','OI'],['NCS','AE']],no=['S1','S1'],ops=[-1,-1],fin=[-1,-1],inv1=[-1,-1],invN=[0,0],date=[20000,20000],chg=[1.25,2.5],teus=[0,0],cbm=[1,2],ckg=[1250,2500],rbuy=[0,0],rsell=[0,0],rbf=[0,0],rsf=[0,0],cols={'p_job':{'d':['=unsafe'], 'pc':[0,0]},'p_lob':{'d':['FFWD AIR EXP'],'pc':[0,0]}},p=dict(co=[0,1],sidx=[0,1],jd=[20000,20000],income=[100,50],expense=[40,70],meta=[]))
 def test_cross_company_identity_totals_and_variance(self):
  d=self.fixture();q=dict(metric='profit.jobs',indices=[0,1],previous_indices=[0]);r=X.execute(d,q,M);self.assertEqual(r['current']['value'],2);self.assertEqual(r['difference'],1)
  q['metric']='profit.gp';r=X.execute(d,q,M);self.assertEqual(r['current']['value'],40);self.assertEqual(r['previous']['value'],60)
  q['metric']='profit.margin';r=X.execute(d,q,M);self.assertAlmostEqual(r['current']['value'],40/150)
 def test_biggest_customer_share_requires_positive_net_gp(self):
  d=self.fixture();d['cols']['customer']={'d':['Alpha','Beta'],'pc':[0,1]}
  r=X.execute(d,dict(metric='profit.biggest_customer',indices=[0,1]),M)
  self.assertAlmostEqual(r['current']['value'],1.5)
  d['p']['expense']=[100,50]
  r=X.execute(d,dict(metric='profit.biggest_customer',indices=[0,1]),M)
  self.assertIsNone(r['current']['value'],'zero net GP has no meaningful concentration denominator')
  d['p']['expense']=[110,60]
  r=X.execute(d,dict(metric='profit.biggest_customer',indices=[0,1]),M)
  self.assertIsNone(r['current']['value'],'negative net GP has no meaningful concentration denominator')
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
  q=dict(metric='profit.expected_cost_only',indices=[1],previous_indices=[]);costs=X.execute(d,q,M)
  self.assertEqual(costs['current']['value'],20);self.assertEqual(costs['records'][0]['expected_cost'],20)
  self.assertEqual(r['previous']['value'],60);self.assertEqual(len(r['benchmark_records']),1)
  self.assertIn('Benchmark Records',load_workbook(io.BytesIO(X.workbook(r))).sheetnames)
 def test_pending_lock_uses_actual_source_stage_label(self):
  d=self.fixture();d['cols']['stage']={'d':['Pending ops lock','Closed'],'c':[0,1]}
  r=X.execute(d,dict(metric='ops.waiting_lock',indices=[0,1]),M)
  self.assertEqual(r['current']['value'],1);self.assertEqual(len(r['records']),1);self.assertEqual(r['records'][0]['source_index'],0)
 def test_workbook_splits_at_excel_limit(self):
  from unittest.mock import patch
  r=X.execute(self.fixture(),dict(metric='profit.gp',indices=[0,1]),M)
  with patch.object(X,'EXCEL_ROW_LIMIT',2):w=load_workbook(io.BytesIO(X.workbook(r)))
  self.assertIn('Contributing Records 2',w.sheetnames)
  total=0
  for name in ['Contributing Records','Contributing Records 2']:
   ws=w[name];headers=[c.value for c in ws[1]];total+=ws.cell(2,headers.index('profit')+1).value
  self.assertEqual(total,40)
 def test_malformed_context_and_nonfinite_expected_values_are_rejected(self):
  for extra in [dict(context=[]),dict(displayed_value=float('inf')),dict(context={'age_as_of':float('inf')}),dict(displayed_value='wrong')]:
   with self.assertRaises(ValueError):X.execute(self.fixture(),dict(metric='ops.shipments',indices=[0],**extra),M)
 def test_operational_evidence_includes_only_unique_matched_jpr_job_lineage(self):
  d=self.fixture()
  d['cols']['p_job']={'d':['JPR-1','JPR-2'],'pc':[0,1]}
  d['cols']['p_lob']={'d':['FFWD AIR EXP','FFWD AIR IMP'],'pc':[0,1]}
  d['cols']['job_owner']={'d':['Owner A','Owner B'],'pc':[0,1]}
  d['p']['sidx']=[0,1]
  d['ops']=[19990,19991]
  d['invN']=[0,0]
  r=X.execute(d,dict(metric='ops.locked_no_invoice',indices=[0]),M)
  self.assertEqual(r['current']['value'],1)
  row=r['records'][0]
  self.assertEqual(row['shipment_no'],'S1')
  self.assertEqual(row['matched_jpr_job_count'],1)
  self.assertEqual(row['matched_jpr_job_numbers'],'JPR-1')
  self.assertEqual(row['matched_jpr_job_dates'],'2024-10-04')
  self.assertEqual(row['matched_jpr_job_lobs'],'FFWD AIR EXP')
  self.assertEqual(row['matched_jpr_job_owners'],'Owner A')
  self.assertEqual(row['jpr_match_status'],'matched')
  wb=load_workbook(io.BytesIO(X.workbook(r)))
  headers=[c.value for c in wb['Contributing Records'][1]]
  self.assertIn('matched_jpr_job_numbers',headers)
  d['user']['finance']=False
  r=X.execute(d,dict(metric='ops.locked_no_invoice',indices=[0]),M)
  self.assertEqual(r['records'][0]['jpr_match_status'],'not available in finance scope')
  self.assertEqual(r['records'][0]['matched_jpr_job_count'],0)
  self.assertEqual(r['records'][0]['matched_jpr_job_numbers'],'')
 def test_locked_no_invoice_evidence_returns_only_locked_uninvoiced_rows(self):
  d=self.fixture();d['ops']=[19999,19998];d['inv1']=[-1,20000];d['invN']=[0,1]
  d['cols']['stage']={'d':['Financials open','Closed'],'pc':[0,1]}
  r=X.execute(d,dict(metric='ops.locked_no_invoice',indices=[0,1],previous_indices=[]),M)
  self.assertEqual(r['current']['value'],1)
  self.assertEqual([row['source_index'] for row in r['records']],[0])

 def test_ops_does_not_include_money(self):
  r=X.execute(self.fixture(),dict(metric='ops.shipments',indices=[0,1]),M);self.assertEqual(r['current']['value'],2);self.assertNotIn('income',r['records'][0])
if __name__=='__main__':unittest.main()
