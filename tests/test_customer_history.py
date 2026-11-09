"""Tests for latest distinct customer job history and owner semantics."""
import unittest
from datetime import date

from app.customer_history import build_recent_jobs


class CustomerHistoryTests(unittest.TestCase):
    def test_returns_five_distinct_jobs_sorted_by_job_date(self):
        rows = [
            {"company": "NG", "customer": "Acme", "job_no": f"J-{n}",
             "job_date": date(2026, 1, n), "lob": "FFWD AIR EXP",
             "extra": {"Job Owner": f"Owner {n}"}}
            for n in range(1, 8)
        ]
        result = build_recent_jobs(rows, lobs=["AE"])
        self.assertEqual(len(result), 5)
        self.assertEqual([row["job_no"] for row in result], ["J-7", "J-6", "J-5", "J-4", "J-3"])
        self.assertEqual(result[0]["job_owner"], "Owner 7")

    def test_same_job_number_in_different_lob_or_company_is_distinct(self):
        rows = [
            {"company": "NG", "customer": "Acme", "job_no": "REUSED",
             "job_date": date(2026, 1, 1), "lob": "FFWD AIR EXP",
             "extra": {"Job Owner": "Air Owner"}},
            {"company": "NG", "customer": "Acme", "job_no": "REUSED",
             "job_date": date(2026, 1, 1), "lob": "FFWD SEA EXP",
             "extra": {"Job Owner": "Sea Owner"}},
            {"company": "NCS", "customer": "Acme", "job_no": "REUSED",
             "job_date": date(2026, 1, 1), "lob": "FFWD AIR EXP",
             "extra": {"Job Owner": "NCS Owner"}},
        ]
        result = build_recent_jobs(rows)
        self.assertEqual(len(result), 3)
        self.assertEqual({row["company"] for row in result}, {"NG", "NCS"})

    def test_missing_owner_is_not_inferred(self):
        row = {"company": "NG", "customer": "Acme", "job_no": "J-1",
               "job_date": date(2026, 1, 1), "lob": "FFWD AIR EXP",
               "extra": {"Job Owner": ""}}
        result = build_recent_jobs([row])
        self.assertEqual(result[0]["job_owner"], "Owner unavailable")
        self.assertEqual(result[0]["owner_status"], "missing")

    def test_conflicting_duplicate_owner_is_not_arbitrarily_selected(self):
        base = {"company": "NG", "customer": "Acme", "job_no": "J-1",
                "job_date": date(2026, 1, 1), "lob": "FFWD AIR EXP"}
        result = build_recent_jobs([
            dict(base, extra={"Job Owner": "Owner A"}),
            dict(base, extra={"Job Owner": "Owner B"}),
        ])
        self.assertEqual(result[0]["job_owner"], "Owner unavailable")
        self.assertEqual(result[0]["owner_status"], "conflicting")

    def test_road_and_general_jobs_are_included_for_unrestricted_scope(self):
        rows = [
            {"company": "NG", "customer": "Acme", "job_no": "R-1",
             "job_date": date(2026, 1, 1), "lob": "FFWD ROAD DOM",
             "extra": {"Job Owner": "Road Owner"}},
            {"company": "NG", "customer": "Acme", "job_no": "G-1",
             "job_date": date(2026, 1, 2), "lob": "GEN",
             "extra": {"Job Owner": "General Owner"}},
        ]
        self.assertEqual(len(build_recent_jobs(rows)), 2)
        self.assertEqual(len(build_recent_jobs(rows, lobs=["AE"])), 0)


if __name__ == "__main__":
    unittest.main()
