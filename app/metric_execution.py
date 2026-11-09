"""Read-only metric evidence over the already permission-scoped dashboard snapshot."""
import hashlib,json,io
from datetime import date,timedelta
from openpyxl import Workbook
from openpyxl.styles import Font

VERSION='1'
def snapshot_id(dataset):
 return hashlib.sha256(json.dumps(dataset,separators=(',',':'),sort_keys=True).encode()).hexdigest()
def value(D,key,i,finance=False):
 c=D.get('cols',{}).get(key,{})
 codes=c.get('pc' if finance else 'c',[])
 return c.get('d',[])[codes[i]] if i<len(codes) else ''
def iso(d):return (date(1970,1,1)+timedelta(days=d)).isoformat() if d is not None and d>=0 else ''
def records(D,source,indices):
 fin=source=='profit';p=D.get('p',{});n=len(p.get('co',[])) if fin else len(D.get('rep',[]))
 if not isinstance(indices,list) or len(indices)>n or any(type(i)is not int or i<0 or i>=n for i in indices):raise ValueError('Invalid scoped record selection.')
 rows=[]
 for i in sorted(set(indices)):
  co=p['co'][i] if fin else int(D['rep'][i]>=4);lob=value(D,'p_lob',i,True) if fin else D['reps'][D['rep'][i]][1]
  r=dict(source_index=i,company=['NG','NCS'][co],lob=lob,job=value(D,'p_job',i,True) if fin else D['no'][i],date=iso(p['jd'][i] if fin else D['date'][i]))
  r.update({k:value(D,k,i,fin) for k in ['branch','customer','shipper','consignee','origin_agent','destination_agent','x_salesperson','origin','destination']})
  if fin:r.update(income=p['income'][i],expense=p['expense'][i],profit=p['income'][i]-p['expense'][i])
  else:r.update(air_weight_t=D['chg'][i] if D['rep'][i]%4<2 else 0,teu=D['teus'][i] if D['rep'][i]%4>=2 else 0,volume_cbm=D['cbm'][i])
  rows.append(r)
 return rows

def aggregate(metric,rows):
 inc=sum(r.get('income',0) for r in rows);exp=sum(r.get('expense',0) for r in rows)
 keys={(r['company'],r['lob'],r['job'],r['date']) for r in rows}
 if metric in ['profit.income','profit.expense','profit.gp']:return {'value':{'profit.income':inc,'profit.expense':exp,'profit.gp':inc-exp}[metric],'numerator':None,'denominator':None}
 if metric=='profit.margin':return dict(value=(inc-exp)/inc if inc>0 else None,numerator=inc-exp,denominator=inc)
 if metric=='profit.cost_coverage':return dict(value=sum(r.get('expense',0)>0 for r in rows)/len(keys) if keys else None,numerator=sum(r.get('expense',0)>0 for r in rows),denominator=len(keys))
 if metric=='profit.expected_adjusted':return dict(value=sum(r.get('profit',0)-r.get('expected_cost',0) for r in rows),numerator=None,denominator=None)
 if metric=='profit.per_job':return dict(value=(inc-exp)/len(keys) if keys else None,numerator=inc-exp,denominator=len(keys))
 if metric in ['profit.jobs','ops.shipments']:return dict(value=len(keys),numerator=None,denominator=None)
 fields={'ops.air_weight':'air_weight_t','ops.teu':'teu','ops.volume':'volume_cbm'}
 if metric in fields:return dict(value=sum(r[fields[metric]] for r in rows),numerator=None,denominator=None)
 raise ValueError('Metric execution is not yet supported.')

def execute(D,body,definitions):
 metric=definitions.get_metric(body.get('metric',''))
 if metric is None:raise ValueError('Unknown metric.')
 source='profit' if metric.id.startswith('profit.') else 'operations'
 if source=='profit' and not D.get('user',{}).get('finance'):raise PermissionError('Finance access required.')
 snap=snapshot_id(D)
 if body.get('snapshot') and body['snapshot']!=snap:raise ValueError('Data snapshot changed. Reload before inspecting or exporting.')
 current=records(D,source,body.get('indices',[]));previous=records(D,source,body.get('previous_indices',[]));benchmark=[]
 if metric.id=='profit.expected_adjusted':
  benchmark=[r for r in records(D,'profit',list(range(len(D['p']['co'])))) if r['income']>0 and r['expense']>0]
  ratios={};ti=te=0
  for r in benchmark:
   a=ratios.setdefault(r['lob'],[0,0]);a[0]+=r['income'];a[1]+=r['expense'];ti+=r['income'];te+=r['expense']
  for r in current+previous:
   a=ratios.get(r['lob']);ratio=a[1]/a[0] if a else te/ti if ti else 0
   r['benchmark_ratio']=ratio;r['expected_cost']=r['income']*ratio if r['income']>0 and r['expense']==0 else 0
 a=aggregate(metric.id,current);b=aggregate(metric.id,previous)
 av,bv=a['value'],b['value'];delta=None if av is None or bv is None else av-bv
 return dict(metric=metric.public_dict(),snapshot=snap,version=VERSION,current=a,previous=b,difference=delta,percentage=None if delta is None or not bv else delta/abs(bv)*100,records=current,comparison_records=previous,benchmark_records=benchmark,context=body.get('context',{}),lineage={'built_at':D.get('built_at'),'reports':D.get('p',{}).get('meta',[]) if source=='profit' else D.get('meta',[])})

def workbook(result):
 wb=Workbook();wb.remove(wb.active)
 def sheet(name,rows):
  ws=wb.create_sheet(name)
  for row in rows:
   ws.append([("'"+v if v[:1] in '=+-@\t\r' else v) if isinstance(v,str) and v else v for v in row])
  ws.freeze_panes='A2';ws.auto_filter.ref=ws.dimensions
  for c in ws[1]:c.font=Font(bold=True)
  for col in ws.columns:ws.column_dimensions[col[0].column_letter].width=min(65,max(14,max(len(str(c.value or '')) for c in col[:100])+2))
  for row in ws.iter_rows(min_row=2):
   for c in row:
    if isinstance(c.value,float):c.number_format='#,##0.00'
 for name,key in [('Contributing Records','records'),('Comparison Records','comparison_records')]+([('Benchmark Records','benchmark_records')] if result.get('benchmark_records') else []):
  rs=result[key];headers=list(rs[0]) if rs else ['No contributing records'];sheet(name,[headers]+[[r.get(k) for k in headers] for r in rs])
 a,b=result['current'],result['previous'];sheet('Reconciliation',[['Item','Value'],['Metric',result['metric']['title']],['Current value',a['value']],['Recalculated value',a['value']],['Difference',0],['Numerator',a['numerator']],['Denominator',a['denominator']],['Comparison value',b['value']],['Absolute variance',result['difference']],['Percentage variance',result['percentage']],['Status','Reconciled to selected scoped snapshot; not independent source audit'],['Formula',result['metric']['formula']]])
 sheet('Metric Definition',[['Attribute','Definition']]+[[k,json.dumps(v) if isinstance(v,(dict,list,tuple)) else v] for k,v in result['metric'].items()])
 sheet('Applied Filters',[['Context','Value']]+[[k,json.dumps(v,ensure_ascii=False)] for k,v in result['context'].items()])
 sheet('Data Lineage',[['Item','Value'],['Snapshot',result['snapshot']],['Metric version',VERSION],['Source metadata',json.dumps(result['lineage'],ensure_ascii=False)]])
 out=io.BytesIO();wb.save(out);return out.getvalue()
