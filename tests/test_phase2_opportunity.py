import unittest
from datetime import date, timedelta
from app.phase2_opportunity import find_opportunities


TODAY = date(2026, 11, 7)


def shipment(company, customer, lob, ident, days=0):
    return {"company": company, "customer": customer, "lob": lob,
            "shipment_id": ident, "shipment_date": TODAY - timedelta(days=days)}


class OpportunityTests(unittest.TestCase):
    def test_cross_sell_whitespace(self):
        rows = [shipment("NG", "C001", "AE", str(i)) for i in range(3)]
        found = find_opportunities(rows, TODAY, complete_lob_coverage=True)
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["candidate_lobs"], ["AI", "OE", "OI"])
        self.assertEqual(found[0]["confidence"], "review_required")

    def test_deduplicate_shipments(self):
        rows = [shipment("NG", "C001", "AE", "1")] * 4
        self.assertEqual(find_opportunities(rows, TODAY), [])

    def test_company_scoped_identity(self):
        rows = [shipment("NG", "C001", "AE", "1"),
                shipment("NCS", "C001", "OI", "2"),
                shipment("NG", "C001", "AE", "3")]
        self.assertEqual(find_opportunities(rows, TODAY), [])

    def test_historical_activity_does_not_count(self):
        rows = [shipment("NG", "C001", "AE", str(i), 300) for i in range(3)]
        self.assertEqual(find_opportunities(rows, TODAY), [])

    def test_unknown_identity_ignored(self):
        rows = [shipment("NG", "", "AE", str(i)) for i in range(3)]
        self.assertEqual(find_opportunities(rows, TODAY), [])

    def test_blank_customer_bucket_is_not_a_whitespace_opportunity(self):
        rows = [shipment("NG", "(blank)", "AE", str(i)) for i in range(3)]
        self.assertEqual(find_opportunities(rows, TODAY, complete_lob_coverage=True), [])

    def test_customer_name_matching_is_case_and_whitespace_insensitive(self):
        rows = [
            shipment("NG", "Acme Logistics", "AE", "1"),
            shipment("NG", " ACME   LOGISTICS ", "AE", "2"),
            shipment("NG", "acme logistics", "AE", "3"),
        ]
        found = find_opportunities(rows, TODAY, complete_lob_coverage=True)
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["shipment_count"], 3)
        self.assertEqual(found[0]["customer"], "Acme Logistics")
    def test_all_services_present_no_whitespace(self):
        rows = [shipment("NG", "C001", lob, lob) for lob in ("AE", "AI", "OE", "OI")]
        self.assertEqual(find_opportunities(rows, TODAY), [])

    def test_partial_scope_produces_no_inference(self):
        rows = [shipment('NG', 'C001', 'AE', str(i)) for i in range(3)]
        self.assertEqual(find_opportunities(rows, TODAY), [])

    def test_bad_window_rejected(self):
        with self.assertRaises(ValueError):
            find_opportunities([], TODAY, window_days=0, complete_lob_coverage=True)


if __name__ == "__main__":
    unittest.main()

class OpportunityIdentityRegression(unittest.TestCase):
 def test_repeated_shipment_number_on_distinct_dates_and_sales_source(self):
  from app.phase2_opportunity import find_opportunities
  from datetime import date
  rows=[dict(company='NG',customer='Acme Logistics',lob='AE',shipment_id='REUSED',shipment_date=date(2026,1,d),salesperson='ERP Sales') for d in [1,2,3]]
  result=find_opportunities(rows,date(2026,1,3),complete_lob_coverage=True)
  self.assertEqual(result[0]['shipment_count'],3);self.assertEqual(result[0]['customer'],'Acme Logistics');self.assertEqual(result[0]['salespersons'],{'ERP Sales':3})
