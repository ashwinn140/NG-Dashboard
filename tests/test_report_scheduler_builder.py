import unittest
from datetime import date
from io import BytesIO

from openpyxl import load_workbook

from app.report_scheduler import (
    REPORT_CATALOG, ScheduleValidationError, build_report_rows,
    build_report_workbook, validate_schedule,
)


def encoded(values):
    dictionary = list(dict.fromkeys(values))
    index = {value: i for i, value in enumerate(dictionary)}
    return {"d": dictionary, "c": [index[value] for value in values],
            "pc": [index[value] for value in values]}


class ReportBuilderTests(unittest.TestCase):
    def dataset(self, finance=False):
        values = {
            "customer": ["Acme"], "branch": ["Mumbai"], "agent": ["Agent A"],
            "x_salesperson": ["Sales A"], "salesperson": ["Sales A"],
            "job_owner": ["Owner A"], "origin": ["Mumbai"], "destination": ["Singapore"],
            "status": ["Open"], "stage": ["Financials open"], "shipper": ["Shipper A"],
            "consignee": ["Consignee A"], "carrier": ["Carrier A"],
            "origin_agent": ["Origin Agent"], "destination_agent": ["Dest Agent"],
            "nomination": ["Self"], "consol": ["Direct"], "cargo": ["General"],
            "x_tradelanename": ["India-Singapore"], "x_loadingcountry": ["India"],
            "x_dischargecountry": ["Singapore"], "x_collectionexecutive": ["Exec"],
            "x_businessdimension": ["Dimension"], "x_incoterms": ["FOB"],
            "x_freighttype": ["Prepaid"], "x_contracttype": ["Spot"],
            "x_commoditytype": ["Textile"], "x_coloadtype": ["Direct"],
            "x_documentexecutiveudf": ["Docs"], "x_placeofexecution": ["Mumbai"],
            "x_containertypes": ["20GP"], "x_bookingthru": ["Self"],
            "p_lob": ["Air Export"], "p_mode": ["Air"], "p_direction": ["Export"],
            "p_kind": ["Freight"], "jp_sales_person": ["Sales A"],
            "p_ic": ["External"], "p_job": ["J-1"], "p_x_tradelanename": ["India-Singapore"],
        }
        cols = {key: encoded(value) for key, value in values.items()}
        return {
            "reps": [["NG", "AE"]], "rep": [0], "no": ["S-1"],
            "date": [date(2026, 11, 5).toordinal() - date(1970, 1, 1).toordinal()],
            "ops": [-1], "fin": [-1], "gross": [1.2], "chg": [1.0],
            "teus": [0.0], "cbm": [2.5], "inv1": [date(2026, 11, 6).toordinal() - date(1970, 1, 1).toordinal()],
            "invN": [1], "rbuy": [10.5], "rbf": [1], "rsell": [12.5], "rsf": [1],
            "cols": cols, "user": {"finance": finance},
            "p": {"co": [0], "jd": [date(2026, 11, 5).toordinal() - date(1970, 1, 1).toordinal()],
                  "td": [date(2026, 11, 6).toordinal() - date(1970, 1, 1).toordinal()],
                  "income": [100.0], "expense": [40.0]},
        }

    def definition(self, report_id="shipment_register", columns=None, filters=None):
        report = REPORT_CATALOG[report_id]
        return {
            "report_id": report_id, "companies": ["NG"], "lobs": ["AE"],
            "filters": filters or {}, "columns": columns or list(report["columns"]),
            "sort": {"field": (columns or list(report["columns"]))[0], "direction": "asc"},
            "summary_detail": "detail", "totals": True,
        }

    def test_customer_performance_summary_excludes_blank_and_normalizes_customer_names(self):
        data = self.dataset()
        day = date(2026, 11, 5).toordinal() - date(1970, 1, 1).toordinal()
        data["rep"] = [0, 0, 0]
        data["no"] = ["S-1", "S-2", "S-3"]
        data["date"] = [day, day + 1, day + 2]
        for key in ("ops", "fin"):
            data[key] = [-1, -1, -1]
        for key in ("gross", "chg", "teus", "cbm", "invN", "rbuy", "rbf", "rsell", "rsf"):
            value = data[key][0]
            data[key] = [value, value, value]
        data["inv1"] = [data["inv1"][0]] * 3
        data["cols"]["customer"] = encoded(["Acme Logistics", "(blank)", " ACME   LOGISTICS "])
        definition = self.definition(
            report_id="customer_performance",
            columns=["customer", "shipments", "air_shipments", "ocean_shipments"],
        )
        definition["summary_detail"] = "summary"
        rows = build_report_rows(data, definition, date(2026, 11, 1), date(2026, 11, 10))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["customer"], "Acme Logistics")
        self.assertEqual(rows[0]["shipments"], 2)
        definition["totals"] = True
        result = build_report_workbook(
            data, definition, date(2026, 11, 1), date(2026, 11, 10), {"status": "fresh"}
        )
        workbook = load_workbook(BytesIO(result["content"]))
        report_sheet = workbook["Report"]
        self.assertEqual(report_sheet["B7"].value, 2)
        self.assertEqual(report_sheet["A8"].value, "TOTAL (includes unassigned)")
        self.assertEqual(report_sheet["B8"].value, 3)
        visuals = workbook["Visuals"]
        self.assertEqual(visuals["B5"].value, 2)
        self.assertEqual(visuals["B6"].value, 1)
        self.assertEqual(visuals["B22"].value, 3)
        self.assertEqual(visuals["B40"].value, 3)
        self.assertIn("B5", visuals._charts[0].series[0].val.numRef.f)
        self.assertIn("A5", visuals._charts[0].series[0].cat.numRef.f)

    def test_shipment_report_exposes_source_dimensions_and_operational_stage(self):
        data = self.dataset()
        definition = self.definition(columns=["shipment_no", "stage", "shipper", "trade_lane",
                                               "invoice_first_date", "invoice_count"])
        rows = build_report_rows(data, definition, date(2026, 11, 1), date(2026, 11, 10))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["stage"], "Financials open")
        self.assertEqual(rows[0]["shipper"], "Shipper A")
        self.assertEqual(rows[0]["trade_lane"], "India-Singapore")
        self.assertEqual(rows[0]["invoice_count"], 1)

    def test_stage_filter_is_applied_to_rows(self):
        data = self.dataset()
        definition = self.definition(columns=["shipment_no", "stage"],
                                     filters={"stage": ["Pending ops lock"]})
        rows = build_report_rows(data, definition, date(2026, 11, 1), date(2026, 11, 10))
        self.assertEqual(rows, [])

    def test_rates_are_hidden_for_non_finance_users(self):
        user = {"id": 1, "companies": ["NG"], "lobs": ["AE"], "finance": False}
        payload = {"report_id": "shipment_register", "companies": ["NG"], "lobs": ["AE"],
                   "columns": ["shipment_no", "buy_rate"]}
        with self.assertRaises(PermissionError):
            validate_schedule(user, payload)

    def test_finance_user_can_include_rates_and_workbook_visuals_sheet(self):
        data = self.dataset(finance=True)
        definition = self.definition(columns=["shipment_no", "buy_rate", "sell_rate"])
        rows = build_report_rows(data, definition, date(2026, 11, 1), date(2026, 11, 10))
        self.assertEqual(rows[0]["buy_rate"], 10.5)
        self.assertEqual(rows[0]["sell_rate"], 12.5)
        result = build_report_workbook(data, definition, date(2026, 11, 1),
                                       date(2026, 11, 10), {"status": "fresh"})
        workbook = load_workbook(BytesIO(result["content"]))
        self.assertIn("Report", workbook.sheetnames)
        self.assertIn("Visuals", workbook.sheetnames)
        self.assertGreaterEqual(len(workbook["Visuals"]._charts), 1)


if __name__ == "__main__":
    unittest.main()
