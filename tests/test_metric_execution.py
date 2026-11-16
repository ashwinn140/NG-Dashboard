import unittest,io,copy
from openpyxl import load_workbook
from app import metric_execution as X,metric_definitions as M
class MetricExecutionTests(unittest.TestCase):
 def fixture(self):
  return dict(user={'finance':True},built_at='test',rep=[0,4],reps=[['NG','AE'],['NG','AI'],['NG','OE'],['NG','OI'],['NCS','AE']],no=['S1','S1'],ops=[-1,-1],fin=[-1,-1],inv1=[-1,-1],invN=[0,0],date=[20000,20000],chg=[1.25,2.5],teus=[0,0],cbm=[1,2],ckg=[1250,2500],rbuy=[0,0],rsell=[0,0],rbf=[0,0],rsf=[0,0],cols={'p_job':{'d':['=unsafe'], 'pc':[0,0]},'p_lob':{'d':['FFWD AIR EXP'],'pc':[0,0]}},p=dict(co=[0,1],sidx=[0,1],jd=[20000,20000],income=[100,50],expense=[40,70],meta=[]))

 def test_rate_usable_evidence_shows_numerator_but_calculates_full_denominator(self):
  d=self.fixture()
  d['ckg']=[1000,1000]
  d['rbuy']=[100,100]
  d['rsell']=[120,110]
  d['rbf']=[1,2]
  d['rsf']=[1,1]
  q=dict(metric='ops.rate_usable',indices=[0,1],previous_indices=[0,1],
         context={'rate_mode':'clean','rate_max':5000})
  r=X.execute(d,q,M)
  self.assertEqual(r['current']['numerator'],1)
  self.assertEqual(r['current']['denominator'],2)
  self.assertEqual(r['current']['value'],0.5)
  self.assertEqual([row['source_index'] for row in r['records']],[0])
  self.assertEqual([row['source_index'] for row in r['comparison_records']],[0])
  q['context']['rate_mode']='text'
  r=X.execute(d,q,M)
  self.assertEqual(r['current']['numerator'],2)
  self.assertEqual(r['current']['denominator'],2)
  self.assertEqual(r['current']['value'],1)
  self.assertEqual([row['source_index'] for row in r['records']],[0,1])

 def test_empty_operations_evidence_does_not_build_unused_finance_lineage(self):
  class ExplodingIndices:
   def __iter__(self):
    raise AssertionError("empty evidence must not traverse the JPR match index")
  d=self.fixture();d['p']['sidx']=ExplodingIndices()
  self.assertEqual(X.records(d,'operations',[]),[])

 def test_activity_evidence_can_skip_expensive_jpr_reverse_lineage(self):
  class ExplodingIndices:
   def __iter__(self):
    raise AssertionError("activity evidence must not build the full JPR reverse index")
   def __getitem__(self,index):
    return 0
  d=self.fixture();d['data_version']=1;d['p']['sidx']=ExplodingIndices()
  result=X.execute(d,dict(metric='ops.shipments',indices=[0]),M,include_operations_links=False)
  self.assertEqual(result['current']['value'],1)
  self.assertEqual(result['records'][0]['source_index'],0)
  with self.assertRaises(AssertionError):
   X.records(d,'operations',[0])
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

 def test_finance_records_expose_matched_and_unmatched_register_lineage(self):
  d=self.fixture();d['p']['sidx']=[0,-1]
  r=X.execute(d,dict(metric='profit.matched_share',indices=[0,1]),M)
  self.assertEqual(r['current']['value'],0.5)
  matched,unmatched=r['records']
  self.assertEqual(matched['jpr_match_status'],'matched')
  self.assertEqual(matched['matched_shipment_no'],'S1')
  self.assertEqual(matched['matched_shipment_date'],'2024-10-04')
  self.assertEqual(unmatched['jpr_match_status'],'unmatched')
  self.assertEqual(unmatched['matched_shipment_no'],'')

 def test_no_finance_and_invalid_selection(self):
  d=self.fixture();d['user']['finance']=False
  with self.assertRaises(PermissionError):X.execute(d,dict(metric='profit.gp',indices=[0]),M)
  for idx in [[2],[-1],[True],['0']]:
   with self.assertRaises(ValueError):X.execute(d,dict(metric='ops.shipments',indices=idx),M)

 def test_snapshot_id_uses_data_version_and_permission_scope(self):
  from app.metric_execution import snapshot_id
  base=dict(data_version=7,built_at='2026-11-10T04:00:00Z',user=dict(companies=['NG'],lobs=['AE'],finance=True),rep=[0,1],p=dict(co=[0]))
  first=snapshot_id(base)
  same_scope=dict(base,rep=[1,0],p=dict(co=[1]))
  self.assertEqual(snapshot_id(same_scope),first,'the version token identifies an immutable dataset; row payloads are not reserialized')
  other_scope=dict(base,user=dict(companies=['NCS'],lobs=['AE'],finance=True))
  self.assertNotEqual(snapshot_id(other_scope),first)
  other_version=dict(base,data_version=8)
  self.assertNotEqual(snapshot_id(other_version),first)
  other_permission=dict(base,user=dict(companies=['NG'],lobs=['AE'],finance=False))
  self.assertNotEqual(snapshot_id(other_permission),first)

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
 def test_blank_customer_buckets_are_excluded_from_named_customer_metrics(self):
  d=self.fixture();d['cols']['customer']={'d':['Alpha','(blank)'],'pc':[0,1],'c':[0,1]}
  r=X.execute(d,dict(metric='profit.customers',indices=[0,1]),M)
  self.assertEqual(r['current']['value'],1)
  self.assertEqual({x['customer'] for x in r['records']},{'Alpha'})
  r=X.execute(d,dict(metric='profit.customers_80',indices=[0,1]),M)
  self.assertEqual(r['current']['value'],1)
  self.assertEqual({x['customer'] for x in r['records']},{'Alpha'})
  r=X.execute(d,dict(metric='profit.loss_customers',indices=[0,1]),M)
  self.assertEqual(r['current']['value'],0)
  self.assertEqual({x['customer'] for x in r['records']},{'Alpha'})
  r=X.execute(d,dict(metric='profit.biggest_customer',indices=[0,1]),M)
  self.assertAlmostEqual(r['current']['value'],1.5)
  self.assertEqual({x['customer'] for x in r['records']},{'Alpha','(blank)'})
  r=X.execute(d,dict(metric='ops.active_customers',indices=[0,1],context={'active_min':1}),M)
  self.assertEqual(r['current']['value'],1)
  self.assertEqual({x['customer'] for x in r['records']},{'Alpha'})
  r=X.execute(d,dict(metric='ops.customer_concentration',indices=[0,1],context={'top_n':1}),M)
  self.assertAlmostEqual(r['current']['value'],0.5)
  self.assertEqual({x['customer'] for x in r['records']},{'Alpha','(blank)'})

 def test_period_customer_metrics_ignore_blank_bucket(self):
  d=self.fixture();d['cols']['customer']={'d':['Alpha','(blank)'],'pc':[0,1],'c':[0,1]}
  r=X.execute(d,dict(metric='ops.period_new_customers',indices=[0,1],previous_indices=[],context={'active_min':1}),M)
  self.assertEqual(r['current']['value'],1)
  self.assertEqual({x['customer'] for x in r['records']},{'Alpha'})
  r=X.execute(d,dict(metric='ops.period_absent_customers',indices=[],previous_indices=[0,1],context={'active_min':1}),M)
  self.assertEqual(r['current']['value'],1)
  self.assertEqual({x['customer'] for x in r['records']},{'Alpha'})

 def test_best_dimension_evidence_excludes_blank_dimension_values(self):
  d=self.fixture();d['cols']['customer']={'d':['Alpha','(blank)'],'pc':[0,1],'c':[0,1]}
  r=X.execute(d,dict(metric='profit.best_dimension',indices=[0,1],context={'dimension_key':'customer'}),M)
  self.assertEqual({x.get('dimension_value') for x in r['records']},{'Alpha'})
 def test_cost_coverage_counts_distinct_jobs(self):
  d=self.fixture();d['p']['co']=[0,0];d['p']['sidx']=[0,1];d['p']['jd']=[20000,20000]
  d['cols']['p_job']={'d':['J1'],'pc':[0,0]}
  d['cols']['p_lob']={'d':['FFWD AIR EXP'],'pc':[0,0]}
  d['p']['expense']=[40,50]
  r=X.execute(d,dict(metric='profit.cost_coverage',indices=[0,1]),M)
  self.assertEqual(r['current']['numerator'],1)
  self.assertEqual(r['current']['denominator'],1)
  self.assertEqual(r['current']['value'],1)

if __name__=='__main__':unittest.main()
