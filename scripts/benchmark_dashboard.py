"""Build a production-sized synthetic dashboard in a fresh temporary database."""
import os
from pathlib import Path
import resource
import sys
import tempfile
import time
from datetime import date

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sqlalchemy import insert
from app.db import get_engine, shipments
from app import dataset as D

os.environ['REPORT_STORAGE_MODE'] = 'replace'
count = 70315
with tempfile.TemporaryDirectory() as temporary:
    engine = get_engine('sqlite:///' + temporary + '/synthetic.db')
    with engine.begin() as c:
        for start in range(0, count, 500):
            batch = []
            for i in range(start, min(start + 500, count)):
                company, report = D.REPS[i % 8]
                day = date(2023 + i % 3, 1 + i % 12, 1 + i % 28)
                extra = {'Shipment No': f'JOB-{i}', 'Shipment Date': str(day),
                         'Customer': f'Customer {i % 1000}', 'Shipper': f'Shipper {i % 700}',
                         'Consignee': f'Consignee {i % 500}', 'Status': 'Open',
                         'Branch': f'Branch {i % 13}', 'Job Owner': f'Owner {i % 30}',
                         'Airline': f'Airline {i % 25}', 'Shipping Line': f'Line {i % 25}',
                         'Gross Weight': '1234', 'Volume': '12.5', 'TEUs': '2',
                         'Loading Port': '(INBOM) Mumbai', 'Discharge Port': '(GBLHR) London'}
                extra.update({f'Unused original ERP column {j}': f'Value {i % 100}' for j in range(100)})
                batch.append(dict(company=company, report_type=report, key=f'JOB-{i}|{day}',
                                  shipment_no=f'JOB-{i}', shipment_date=day, from_import=1, extra=extra))
            c.execute(insert(shipments), batch)
    started = time.monotonic()
    result = D.build_full(engine)
    assert len(result['rep']) == count
    assert result['changes'] == {}
    print(f'Built {count:,} synthetic shipment rows in {time.monotonic() - started:.2f}s')
    print(f'Process peak RSS: {resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024:.1f} MiB')
    print('Includes 100 unused original ERP columns per row; all remain stored.')
    engine.dispose()
