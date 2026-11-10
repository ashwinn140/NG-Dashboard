"""Read-only metric evidence over the already permission-scoped dashboard snapshot."""
import hashlib,json,io,math
from datetime import date,timedelta
from openpyxl import Workbook
from openpyxl.styles import Font

VERSION='1'
EXCEL_ROW_LIMIT=1048576
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
 # Reverse the dataset's already-validated unique JPR -> shipment-register match.
 # This is an evidence link only; it does not create a new or guessed match.
 matched_jpr={}
 if not fin and D.get('user',{}).get('finance'):
  jp=D.get('p',{})
  for j,si in enumerate(jp.get('sidx',[])):
   if type(si) is int and si>=0:
    matched_jpr.setdefault(si,[]).append({
     'job':value(D,'p_job',j,True),
     'job_date':iso(jp.get('jd',[])[j] if j<len(jp.get('jd',[])) else -1),
     'lob':value(D,'p_lob',j,True),
     'job_owner':value(D,'job_owner',j,True),
    })
 for i in sorted(set(indices)):
  co=p['co'][i] if fin else int(D['rep'][i]>=4);lob=value(D,'p_lob',i,True) if fin else D['reps'][D['rep'][i]][1]
  r=dict(source_index=i,company=['NG','NCS'][co],lob=lob,job=value(D,'p_job',i,True) if fin else D['no'][i],date=iso(p['jd'][i] if fin else D['date'][i]))
  r.update({k:value(D,k,i,fin) for k in ['branch','customer','shipper','consignee','origin_agent','destination_agent','x_salesperson','origin','destination','stage','p_ic']})
  if fin:
   si=p['sidx'][i]
   matched=type(si) is int and 0<=si<len(D.get('no',[]))
   r.update(matched_source_index=si,jpr_match_status='matched' if matched else 'unmatched',
            matched_shipment_no=D['no'][si] if matched else '',
            matched_shipment_date=iso(D['date'][si]) if matched and si<len(D.get('date',[])) else '',
            income=p['income'][i],expense=p['expense'][i],profit=p['income'][i]-p['expense'][i])
  else:
   links=matched_jpr.get(i,[])
   r.update(shipment_no=D['no'][i],report_index=D['rep'][i],shipment_day=D['date'][i],operations_lock_day=D['ops'][i],financial_lock_day=D['fin'][i],invoice_day=D['inv1'][i],invoice_count=D['invN'][i],first_invoice_date=iso(D['inv1'][i]),operations_lock_date=iso(D['ops'][i]),financial_lock_date=iso(D['fin'][i]),air_weight_t=D['chg'][i] if D['rep'][i]%4<2 else 0,teu=D['teus'][i] if D['rep'][i]%4>=2 else 0,volume_cbm=D['cbm'][i],matched_jpr_job_count=len(links),matched_jpr_job_numbers='; '.join(str(x['job']) for x in links if x['job']),matched_jpr_job_dates='; '.join(x['job_date'] for x in links if x['job_date']),matched_jpr_job_lobs='; '.join(x['lob'] for x in links if x['lob']),matched_jpr_job_owners='; '.join(x['job_owner'] for x in links if x['job_owner']),jpr_match_status=('matched' if links else 'no unique JPR match') if D.get('user',{}).get('finance') else 'not available in finance scope')
  if D.get('user',{}).get('finance'):
   si=p['sidx'][i] if fin else i
   if si>=0:
    r.update(register_report=D['rep'][si],chargeable_kg=D['ckg'][si],matched_air_t=D['chg'][si] if D['rep'][si]%4<2 else 0,matched_teu=D['teus'][si] if D['rep'][si]%4>=2 else 0,buy_rate=D['rbuy'][si],sell_rate=D['rsell'][si],buy_flag=D['rbf'][si],sell_flag=D['rsf'][si])
  rows.append(r)
 return rows

def usable_rate(r,options):
 ok=lambda f:f==1 or f==2 and options.get('rate_mode','text')!='clean'
 return r.get('register_report',-1)%4==0 and r.get('chargeable_kg',0)>0 and ok(r.get('buy_flag',0)) and ok(r.get('sell_flag',0)) and 0<r.get('buy_rate',0)<=float(options.get('rate_max',5000)) and 0<r.get('sell_rate',0)<=float(options.get('rate_max',5000))

def aggregate(metric,rows,options=None):
 options=options or {}
 inc=sum(r.get('income',0) for r in rows);exp=sum(r.get('expense',0) for r in rows)
 keys={(r['company'],r['lob'],r['job'],r['date']) for r in rows}
 if metric.startswith('ops.rate_') or metric.startswith('profit.rate_matched_'):
  ae=[r for r in rows if r.get('register_report',-1)%4==0];eligible=[r for r in ae if usable_rate(r,options)]
  kg=sum(r['chargeable_kg'] for r in eligible);sell=sum(r['sell_rate']*r['chargeable_kg'] for r in eligible);buy=sum(r['buy_rate']*r['chargeable_kg'] for r in eligible);gp=sum(r.get('profit',0) for r in eligible)
  if metric=='ops.rate_air_exports':v=len(ae);num=den=None
  elif metric=='ops.rate_usable':num=len(eligible);den=len(ae);v=num/den if den else None
  elif metric in ['ops.rate_sell','ops.rate_buy','ops.rate_margin_kg']:num=sell if metric=='ops.rate_sell' else buy if metric=='ops.rate_buy' else sell-buy;den=kg;v=num/den if den else None
  else:num=den=None;v={'ops.rate_margin':sell-buy,'ops.rate_below_buy':sum(r['sell_rate']<r['buy_rate'] for r in eligible),'profit.rate_matched_count':len(eligible),'profit.rate_matched_estimate':sell-buy,'profit.rate_matched_actual':gp,'profit.rate_matched_difference':gp-(sell-buy)}[metric]
  return dict(value=v,numerator=num,denominator=den)
 if metric in ['profit.air_yield','profit.ocean_yield','profit.matched_share','profit.best_dimension']:
  if metric=='profit.best_dimension':
   grouped={}
   for r in rows:grouped[r.get('dimension_value','')]=grouped.get(r.get('dimension_value',''),0)+r['profit']
   return dict(value=max([v for v in grouped.values() if v>0],default=None),numerator=None,denominator=None)
  if metric=='profit.matched_share':num=sum(r['matched_source_index']>=0 for r in rows);den=len(rows)
  else:
   air=metric=='profit.air_yield';matched=[r for r in rows if r.get('matched_source_index',-1)>=0 and (r.get('register_report',-1)%4<2)==air];num=sum(r['profit'] for r in matched);den=sum(r.get('matched_air_t' if air else 'matched_teu',0) for r in matched)
  return dict(value=num/den if den>0 else None,numerator=num,denominator=den)
 if metric in ['profit.customers','profit.customers_80','profit.biggest_customer','profit.loss_customers']:
  grouped={}
  for r in rows:grouped[r['customer']]=grouped.get(r['customer'],0)+r['profit']
  profits=sorted(grouped.values(),reverse=True);pos=sum(x for x in profits if x>0);cum=n=0
  for x in profits:
   if x>0 and cum<.8*pos:cum+=x;n+=1
  v={'profit.customers':len(grouped),'profit.customers_80':n,'profit.biggest_customer':profits[0]/sum(profits) if profits and sum(profits)>0 else None,'profit.loss_customers':sum(x<0 for x in profits)}[metric]
  return dict(value=v,numerator=None,denominator=None)
 if metric=='ops.customer_concentration':
  grouped={};measure=options.get('concentration_measure','count')
  for r in rows:grouped[r['customer']]=grouped.get(r['customer'],0)+(1 if measure=='count' else r.get(measure,0))
  total=sum(grouped.values());num=sum(sorted(grouped.values(),reverse=True)[:max(1,int(options.get('top_n',25)))]);return dict(value=num/total if total else None,numerator=num,denominator=total)
 if metric in ['profit.cost_not_booked_proxy','profit.billing_pending_proxy','profit.loss_making','profit.low_margin','profit.negative_income_rows','profit.intercompany_proxy']:return dict(value=len(rows),numerator=None,denominator=None)
 if metric=='ops.invoice_reference_count' or metric=='profit.rows':return dict(value=len(rows),numerator=None,denominator=None)
 if metric=='ops.invoiced_count':return dict(value=len(rows),numerator=None,denominator=None)
 if metric=='ops.active_customers':
  counts={}
  for r in rows:counts[r['customer']]=counts.get(r['customer'],0)+1
  return dict(value=sum(n>=max(1,int(options.get('active_min',1))) for n in counts.values()),numerator=None,denominator=None)
 if metric.startswith('ops.') and metric not in ['ops.shipments','ops.air_weight','ops.air_weight_kg','ops.teu','ops.volume','ops.period_new_customers','ops.period_absent_customers']:
  today=int(options.get('age_as_of',0));old=int(options.get('old_days',90));unbilled=int(options.get('unbilled_days',30));eligible=rows;numerator=denominator=None
  if metric=='ops.waiting_lock':eligible=[r for r in rows if r['stage']=='Pending ops lock'];v=len(eligible)
  elif metric=='ops.financials_open':eligible=[r for r in rows if r['stage']=='Financials open'];v=len(eligible)
  elif metric=='ops.old_open':eligible=[r for r in rows if r['stage']!='Closed' and today-r['shipment_day']>old];v=len(eligible)
  elif metric=='ops.oldest_open':eligible=[r for r in rows if r['stage']!='Closed'];v=max([today-r['shipment_day'] for r in eligible]+[0])
  elif metric=='ops.lock_lag':eligible=[r for r in rows if r['operations_lock_day']>0 and r['financial_lock_day']>0];numerator=sum(r['financial_lock_day']-r['operations_lock_day'] for r in eligible);denominator=len(eligible);v=numerator/denominator if denominator else None
  elif metric=='ops.invoiced_share':numerator=sum(r['invoice_count']>0 for r in rows);denominator=len(rows);v=numerator/denominator if denominator else None
  elif metric in ['ops.invoice_lag','ops.lock_invoice_lag']:
   eligible=[r for r in rows if r['invoice_count']>0 and r['invoice_day']>0 and (metric=='ops.invoice_lag' or r['operations_lock_day']>0)];numerator=sum(r['invoice_day']-(r['shipment_day'] if metric=='ops.invoice_lag' else r['operations_lock_day']) for r in eligible);denominator=len(eligible);v=numerator/denominator if denominator else None
  elif metric=='ops.operations_locked':eligible=[r for r in rows if r['operations_lock_day']>0];v=len(eligible)
  elif metric in ['ops.locked_no_invoice','ops.overdue_invoice']:eligible=[r for r in rows if r['operations_lock_day']>0 and r['invoice_count']==0 and (metric=='ops.locked_no_invoice' or today-r['operations_lock_day']>unbilled)];v=len(eligible)
  else:raise ValueError('Unsupported operational metric.')
  return dict(value=v,numerator=numerator,denominator=denominator)
 if metric in ['ops.period_new_customers','ops.period_absent_customers']:return dict(value=len({r['customer'] for r in rows}),numerator=None,denominator=None)
 if metric in ['profit.income','profit.expense','profit.gp']:return {'value':{'profit.income':inc,'profit.expense':exp,'profit.gp':inc-exp}[metric],'numerator':None,'denominator':None}
 if metric=='profit.margin':return dict(value=(inc-exp)/inc if inc>0 else None,numerator=inc-exp,denominator=inc)
 if metric=='profit.cost_coverage':return dict(value=sum(r.get('expense',0)>0 for r in rows)/len(keys) if keys else None,numerator=sum(r.get('expense',0)>0 for r in rows),denominator=len(keys))
 if metric=='profit.expected_adjusted':return dict(value=sum(r.get('profit',0)-r.get('expected_cost',0) for r in rows),numerator=None,denominator=None)
 if metric=='profit.expected_cost_only':return dict(value=sum(r.get('expected_cost',0) for r in rows),numerator=None,denominator=None)
 if metric=='profit.per_job':return dict(value=(inc-exp)/len(keys) if keys else None,numerator=inc-exp,denominator=len(keys))
 if metric in ['profit.jobs','ops.shipments']:return dict(value=len(keys),numerator=None,denominator=None)
 if metric=='ops.air_weight_kg':return dict(value=sum(r['air_weight_t']*1000 for r in rows),numerator=None,denominator=None)
 fields={'ops.air_weight':'air_weight_t','ops.teu':'teu','ops.volume':'volume_cbm'}
 if metric in fields:return dict(value=sum(r[fields[metric]] for r in rows),numerator=None,denominator=None)
 raise ValueError('Metric execution is not yet supported.')

def eligible_records(metric, rows, context):
 today=int(context.get('age_as_of',0));old=int(context.get('old_days',90));late=int(context.get('unbilled_days',30))
 predicates={
 'ops.air_weight':lambda r:r['report_index']%4<2,
 'ops.air_weight_kg':lambda r:r['report_index']%4<2,
 'ops.teu':lambda r:r['report_index']%4>=2,
 'ops.invoice_reference_count':lambda r:r['invoice_count']>0,
 'ops.invoiced_count':lambda r:r['invoice_day']>0,
 'profit.cost_not_booked_proxy':lambda r:r['income']>0 and r['expense']==0,
 'profit.expected_cost_only':lambda r:r['income']>0 and r['expense']==0,
 'profit.billing_pending_proxy':lambda r:r['income']<=0 and r['expense']>0,
 'profit.loss_making':lambda r:r['profit'] < -1 and not(r['income']<=0 and r['expense']>0),
 'profit.low_margin':lambda r:r['income']>0 and r['expense']!=0 and r['profit']>=-1 and r['profit']/r['income'] < float(context.get('low_margin',10))/100,
 'profit.negative_income_rows':lambda r:r['income']<0,
 'profit.intercompany_proxy':lambda r:r['p_ic']=='Intercompany',
 'ops.waiting_lock':lambda r:r['stage']=='Pending ops lock',
 'ops.financials_open':lambda r:r['stage']=='Financials open',
 'ops.old_open':lambda r:r['stage']!='Closed' and today-r['shipment_day']>old,
 'ops.oldest_open':lambda r:r['stage']!='Closed',
 'ops.lock_lag':lambda r:r['operations_lock_day']>0 and r['financial_lock_day']>0,
 'ops.invoice_lag':lambda r:r['invoice_count']>0 and r['invoice_day']>0,
 'ops.lock_invoice_lag':lambda r:r['invoice_count']>0 and r['invoice_day']>0 and r['operations_lock_day']>0,
 'ops.operations_locked':lambda r:r['operations_lock_day']>0,
 'ops.locked_no_invoice':lambda r:r['operations_lock_day']>0 and r['invoice_count']==0,
 'ops.overdue_invoice':lambda r:r['operations_lock_day']>0 and r['invoice_count']==0 and today-r['operations_lock_day']>late}
 if metric.startswith('ops.rate_'):
  rows=[r for r in rows if r.get('register_report',-1)%4==0]
  if metric not in ['ops.rate_air_exports','ops.rate_usable']:rows=[r for r in rows if usable_rate(r,context) and (metric!='ops.rate_below_buy' or r['sell_rate']<r['buy_rate'])]
 if metric.startswith('profit.rate_matched_'):rows=[r for r in rows if usable_rate(r,context)]
 if metric in ['profit.air_yield','profit.ocean_yield']:rows=[r for r in rows if r.get('matched_source_index',-1)>=0 and (r.get('register_report',-1)%4<2)==(metric=='profit.air_yield')]
 return [r for r in rows if predicates[metric](r)] if metric in predicates else rows

def execute(D,body,definitions):
 if not isinstance(body,dict) or not isinstance(body.get('context',{}),dict):raise ValueError('Metric context must be an object.')
 displayed=body.get('displayed_value')
 if displayed is not None and (type(displayed) not in (int,float) or not math.isfinite(displayed)):raise ValueError('Displayed value must be a finite number or null.')
 for key in ['active_min','old_days','unbilled_days','age_as_of','rate_max','low_margin','top_n']:
  val=body.get('context',{}).get(key)
  if val is not None and (type(val) not in (int,float) or not math.isfinite(val) or val<0 or val>1e9):raise ValueError('Invalid metric threshold.')
 metric=definitions.get_metric(body.get('metric',''))
 if metric is None:raise ValueError('Unknown metric.')
 source='profit' if metric.id.startswith('profit.') else 'operations'
 if metric.public_dict()['finance_required'] and not D.get('user',{}).get('finance'):raise PermissionError('Finance access required.')
 if body.get('dataset_built_at') and body['dataset_built_at']!=D.get('built_at'):raise ValueError('Dashboard data changed. Reload before inspecting records.')
 snap=snapshot_id(D)
 if body.get('snapshot') and body['snapshot']!=snap:raise ValueError('Data snapshot changed. Reload before inspecting or exporting.')
 current=eligible_records(metric.id,records(D,source,body.get('indices',[])),body.get('context',{}));previous=eligible_records(metric.id,records(D,source,body.get('previous_indices',[])),body.get('context',{}));operations_records=records(D,'operations',body.get('ops_indices',[]));benchmark=[]
 if metric.id in ['profit.expected_adjusted','profit.expected_cost_only']:
  benchmark=[r for r in records(D,'profit',list(range(len(D['p']['co'])))) if r['income']>0 and r['expense']>0]
  ratios={};ti=te=0
  for r in benchmark:
   a=ratios.setdefault(r['lob'],[0,0]);a[0]+=r['income'];a[1]+=r['expense'];ti+=r['income'];te+=r['expense']
  for r in current+previous:
   a=ratios.get(r['lob']);ratio=a[1]/a[0] if a else te/ti if ti else 0
   r['benchmark_ratio']=ratio;r['expected_cost']=r['income']*ratio if r['income']>0 and r['expense']==0 else 0
 for r in current+previous:
  if body.get('context',{}).get('dimension_key'):r['dimension_value']=value(D,body['context']['dimension_key'],r['source_index'],source=='profit')
 if metric.id in ['ops.period_new_customers','ops.period_absent_customers']:
  ca={};pa={};minimum=max(1,int(body.get('context',{}).get('active_min',1)))
  for r in current:ca[r['customer']]=ca.get(r['customer'],0)+1
  for r in previous:pa[r['customer']]=pa.get(r['customer'],0)+1
  chosen={c for c,n in (ca if metric.id=='ops.period_new_customers' else pa).items() if n>=minimum and not (pa if metric.id=='ops.period_new_customers' else ca).get(c)}
  current=[r for r in (current if metric.id=='ops.period_new_customers' else previous) if r['customer'] in chosen];previous=[]
 a=aggregate(metric.id,current,body.get('context'));b=aggregate(metric.id,previous,body.get('context'))
 if body.get('compare') is False or metric.id in ['ops.period_new_customers','ops.period_absent_customers']:b=dict(value=None,numerator=None,denominator=None)
 av,bv=a['value'],b['value'];delta=None if av is None or bv is None else av-bv
 displayed=body.get('displayed_value',a['value']);difference=None if displayed is None or a['value'] is None else displayed-a['value']
 reconciliation=dict(displayed_value=displayed,recalculated_value=a['value'],difference=difference,status='match' if difference is not None and abs(difference)<0.005 else 'not comparable' if difference is None else 'mismatch')
 return dict(reconciliation=reconciliation,metric=metric.public_dict(),snapshot=snap,version=VERSION,current=a,previous=b,difference=delta,percentage=None if delta is None or not bv else delta/abs(bv)*100,records=current,comparison_records=previous,operations_records=operations_records,benchmark_records=benchmark,context=body.get('context',{}),lineage={'built_at':D.get('built_at'),'reports':D.get('p',{}).get('meta',[]) if source=='profit' else D.get('meta',[])})

def workbook(result):
 wb=Workbook(write_only=True)
 def sheet(name,rows):
  from openpyxl.cell import WriteOnlyCell
  from openpyxl.utils import get_column_letter
  it=iter(rows);headers=next(it,[]);ws=None;count=0;part=0
  def create():
   nonlocal ws,count,part
   if ws is not None:ws.auto_filter.ref='A1:'+get_column_letter(max(1,len(headers)))+str(count)
   part+=1;ws=wb.create_sheet((name if part==1 else name[:26]+' '+str(part))[:31]);ws.freeze_panes='A2';count=1
   for i,label in enumerate(headers,1):ws.column_dimensions[get_column_letter(i)].width=min(48,max(16,len(str(label))+3))
   cells=[]
   for v in headers:c=WriteOnlyCell(ws,value=v);c.font=Font(bold=True);cells.append(c)
   ws.append(cells)
  create()
  for row in it:
   if count>=EXCEL_ROW_LIMIT:create()
   cells=[]
   for i,v in enumerate(row):
    if isinstance(v,str) and v:
     if v.lstrip()[:1] and v.lstrip()[:1] in '=+-@' or v[:1] in '\t\r':v="'"+v
     elif i<len(headers) and headers[i]=='date':
      try:v=date.fromisoformat(v)
      except ValueError:pass
    c=WriteOnlyCell(ws,value=v)
    if isinstance(v,float):c.number_format='#,##0.00'
    if isinstance(v,date):c.number_format='dd-mmm-yyyy'
    cells.append(c)
   ws.append(cells);count+=1
  ws.auto_filter.ref='A1:'+get_column_letter(max(1,len(headers)))+str(count)
 for name,key in [('Contributing Records','records'),('Comparison Records','comparison_records')]+([('Operational Records','operations_records')] if result.get('operations_records') else [])+([('Benchmark Records','benchmark_records')] if result.get('benchmark_records') else []):
  rs=result[key];headers=list(rs[0]) if rs else ['No contributing records'];from itertools import chain
  sheet(name,chain([headers],([r.get(k) for k in headers] for r in rs)))
 a,b=result['current'],result['previous'];sheet('Reconciliation',[['Item','Value'],['Metric',result['metric']['title']],['Current value',result['reconciliation']['displayed_value']],['Recalculated value',a['value']],['Difference',result['reconciliation']['difference']],['Numerator',a['numerator']],['Denominator',a['denominator']],['Comparison value',b['value']],['Absolute variance',result['difference']],['Percentage variance',result['percentage']],['Status',result['reconciliation']['status']+' · authorized snapshot; independent accepted-source audit pending'],['Formula',result['metric']['formula']]])
 sheet('Metric Definition',[['Attribute','Definition']]+[[k,json.dumps(v) if isinstance(v,(dict,list,tuple)) else v] for k,v in result['metric'].items()])
 sheet('Applied Filters',[['Context','Value']]+[[k,json.dumps(v,ensure_ascii=False)] for k,v in result['context'].items()])
 sheet('Data Lineage',[['Item','Value'],['Snapshot',result['snapshot']],['Metric version',VERSION],['Source metadata',json.dumps(result['lineage'],ensure_ascii=False)]])
 out=io.BytesIO();wb.save(out);return out.getvalue()
