import unittest

from app import dataset as DS


class TestRestrictedReportMetadata(unittest.TestCase):
    def test_out_of_scope_report_metadata_has_no_dates_or_counts(self):
        full = {
            "reps": [("NG", "AE"), ("NCS", "OE")],
            "rep": [0, 1],
            "no": ["S1", "S2"],
            "date": [20000, 20001],
            "ops": [0, 0], "fin": [0, 0], "gross": [0, 0],
            "chg": [0, 0], "teus": [0, 0], "cbm": [0, 0], "ckg": [0, 0],
            "rbuy": [0, 0], "rbf": [0, 0], "rsell": [0, 0], "rsf": [0, 0],
            "inv1": [0, 0], "invN": [0, 0],
            "p": {"co": [], "rt": [], "sidx": [], "income": [], "expense": [], "td": [], "jd": [], "meta": []},
            "cols": {"agent": {"l": "Agent", "d": ["Agent"], "c": [0, 0], "pc": []}},
            "agentInfo": [["", "", "", "", "", ""]],
            "meta": [
                {"co": "NG", "rows": 12, "from": "2026-01-01", "to": "2026-11-01", "range_from": "2026-01-01", "range_to": "2026-11-01", "pend": 2, "finopen": 3, "repeated": 1, "runs": 4},
                {"co": "NCS", "rows": 99, "from": "2024-01-01", "to": "2026-10-31", "range_from": "2024-01-01", "range_to": "2026-10-31", "pend": 9, "finopen": 8, "repeated": 7, "runs": 6},
            ],
            "changes": {},
        }
        restricted = DS.restrict(full, {"companies": ["NG"], "lobs": ["AE"], "finance": False})
        hidden = restricted["meta"][1]
        self.assertTrue(hidden["restricted"])
        self.assertEqual(hidden["rows"], 0)
        self.assertEqual(hidden["runs"], 0)
        self.assertEqual(hidden["range_from"], "")
        self.assertEqual(hidden["range_to"], "")
        self.assertEqual(hidden["from"], "")
        self.assertEqual(hidden["to"], "")
        self.assertEqual(hidden["pend"], 0)
        self.assertEqual(hidden["finopen"], 0)


if __name__ == "__main__":
    unittest.main()
