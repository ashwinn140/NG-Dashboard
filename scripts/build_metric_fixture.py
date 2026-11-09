"""Synthetic metric/UI/export fixtures. No production access."""
import json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app import metric_execution as X,metric_definitions as M
source=Path('/tmp/ng-fixture-admin.json')
D=json.loads(source.read_text());q={"metric":"profit.gp","indices":list(range(len(D["p"]["co"]))),"previous_indices":[],"context":{"data":"Synthetic example; not company financial results"}}
r=X.execute(D,q,M)
Path('/tmp/metric-ui-evidence.json').write_text(json.dumps(r))
Path('/tmp/NG_Synthetic_Reconciliation.xlsx').write_bytes(X.workbook(r))
print('Synthetic metric drawer fixture and reconciliation workbook written.')
