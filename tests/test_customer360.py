"""Customer360 source roles, authentication and private saved-view permissions."""
import unittest
from app import dataset as D, auth
from app.server import create_app
from fastapi.testclient import TestClient
from scripts.test_daily_replacement import ReplacementTests as Fixture

class Customer360Tests(unittest.TestCase):
 def setUp(self): self.f=Fixture();self.f.setUp()
 def tearDown(self): self.f.tearDown()
 def test_explicit_roles_and_absent_field_fallback(self):
  f=self.f;r=f.register();r.df['Origin Agent']=['Origin A','Origin B'];r.df['Destination Agent']=['Dest A','Dest B'];r.df['Booking Thru']='Generic agent';f.load(r)
  p=f.profit();p.df.loc[0,'Job No.']='JOB-0';p.df.loc[1,'Job No.']='JOB-1';p.df['Origin Agent']=['Source Origin','','Unknown'];p.df['Overseas Agent']='Generic overseas';f.load_profit(p)
  ds=D.build_full(f.engine);dec=lambda k,i,src:ds['cols'][k]['d'][ds['cols'][k][src][i]]
  self.assertEqual(dec('origin_agent',0,'c'),'Origin A');self.assertEqual(dec('destination_agent',0,'c'),'Dest A')
  self.assertEqual(dec('origin_agent',0,'pc'),'Source Origin');self.assertEqual(dec('origin_agent',1,'pc'),'(blank)');self.assertEqual(dec('destination_agent',0,'pc'),'Dest A')
  self.assertNotIn('Generic overseas',ds['cols']['destination_agent']['d'])
  scoped=D.restrict(ds,dict(companies=['NG'],lobs=['AE'],finance=False));self.assertEqual(scoped['p']['income'],[]);self.assertEqual(scoped['cols']['origin_agent']['pc'],[])
 def test_regular_user_route_and_saved_view_isolation(self):
  f=self.f;app=create_app(f.engine,f.tmp.name+'/up')
  try:
   one,two=TestClient(app),TestClient(app)
   self.assertEqual(one.get('/customer360',follow_redirects=False).status_code,303)
   for i,client in enumerate([one,two]):
    email=f'user{i}@example.test';auth.create_user(f.engine,email,'operations','User',companies=['NG'],lobs=['AE'],finance=False,password='Synthetic-pass123')
    self.assertEqual(client.post('/auth/login',json=dict(login=email,password='Synthetic-pass123')).status_code,200)
    self.assertEqual(client.get('/customer360').status_code,200)
   self.assertEqual(one.put('/api/prefs/partner360',json={'My view':{}}).status_code,403)
   csrf=one.get('/api/me').json()['csrf'];self.assertEqual(one.put('/api/prefs/partner360',headers={'X-CSRF-Token':csrf},json={'My view':{}}).status_code,200)
   self.assertEqual(one.get('/api/prefs').json()['partner360'],{'My view':{}});self.assertNotIn('partner360',two.get('/api/prefs').json())
  finally:app.state.store.stop=True;app.state.store.wake.set()

if __name__=='__main__':unittest.main()
