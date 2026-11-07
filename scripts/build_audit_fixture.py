"""Build synthetic NG/NCS ERP datasets in /tmp; never connects to production."""
import sys,json
sys.path.insert(0,str(__import__('pathlib').Path(__file__).resolve().parents[1]))
from scripts.test_daily_replacement import ReplacementTests
from app import dataset as D
import pandas as pd
from datetime import date
from pathlib import Path
f=ReplacementTests();f.setUp()
try:
 for co in ['NG','NCS']:
  for lob in ['AE','AI','OE','OI']:
   for year in [2025,2026]:
    r=f.register(year,customers=tuple('Customer '+str(i%3) for i in range(12)));r.company=co;r.report_type=lob
    for i in range(12):
     r.df.loc[i,'Shipment No']=co+'-'+lob+'-'+str(i)
     r.df.loc[i,'Shipment Date']=pd.Timestamp(year,i%10+1,1)
     for k,v in {'Sales Person':'Sales '+str(i%2),'Chargeable Wt':1000+i*25.3,'TEUs':1.5,'Volume':2.35,'Loading Port':'(INBOM) Mumbai','Discharge Port':'(USNYC) New York','Shipping Line':'Line','Self/Agent Nomination (UDF)':['Agent Nomination','Self Nomination','Sub Agent'][i%3],'Booking Thru':'Self','Buy Rate (UDF)':10,'Sell Rate (UDF)':20,'Operations Locked On':pd.Timestamp(year,i%10+1,2)}.items():r.df.loc[i,k]=v
    assert f.load(r)['status']=='promoted'
  for year in [2025,2026]:
   p=f.profit(year);p.company=co;p.df=pd.concat([p.df]*4,ignore_index=True)
   for i in range(12):
    lob=['AE','AI','OE','OI'][i%4];p.df.loc[i,'Job No.']=co+'-'+lob+'-'+str(i);p.df.loc[i,'LOB']={'AE':'AIR EXPORT','AI':'AIR IMPORT','OE':'SEA EXPORT','OI':'SEA IMPORT'}[lob];p.df.loc[i,'Job Date']=pd.Timestamp(year,i%10+1,1);p.df.loc[i,'Date']=pd.Timestamp(year,i%10+1,3);p.df.loc[i,'Income (INR)']=100+i*10;p.df.loc[i,'Expense (INR)']=50+i
   assert f.load_profit(p)['status']=='promoted'
 ds=D.build_full(f.engine)
 for name,u in [('admin',dict(companies=[],lobs=[],finance=True)),('ops',dict(companies=['NG'],lobs=['AE'],finance=False)),('finance',dict(companies=['NCS'],lobs=['OI'],finance=True))]:Path('/tmp/ng-fixture-'+name+'.json').write_text(json.dumps(D.restrict(ds,u)))
 print('Fixture',len(ds['rep']),'shipments',len(ds['p']['co']),'finance lines',sum(ds['p']['income']),sum(ds['p']['expense']))
finally:f.tearDown()
