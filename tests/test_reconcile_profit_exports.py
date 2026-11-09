"""Regression tests for read-only source-to-DB financial reconciliation."""
import csv
import tempfile
import unittest
from pathlib import Path

from scripts.reconcile_profit_exports import reconcile

HEADER = ["company", "job_no", "job_date", "lob", "income", "expense", "profit"]


def write(path, rows):
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(HEADER)
        writer.writerows(rows)


class ReconciliationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.source = Path(self.temp.name) / "source.csv"
        self.database = Path(self.temp.name) / "database.csv"
        self.one = ["NG", "JOB1", "2024-01-03", "AIR EXPORT", "100", "70", "30"]
        self.two = ["NCS", "JOB2", "2024-01-04", "SEA IMPORT", "250", "100", "150"]

    def test_identical_exports_match(self):
        write(self.source, [self.one, self.two])
        write(self.database, [self.two, self.one])
        result = reconcile(self.source, self.database)
        self.assertEqual(result["status"], "matched")
        self.assertEqual(result["source_count"], 2)
        self.assertEqual(result["source_totals"]["profit"], "180.00")

    def test_missing_and_extra_jobs_are_reported(self):
        write(self.source, [self.one])
        write(self.database, [self.two])
        result = reconcile(self.source, self.database)
        self.assertEqual(result["status"], "mismatch")
        self.assertEqual(len(result["missing_in_database"]), 1)
        self.assertEqual(len(result["unexpected_in_database"]), 1)

    def test_amount_discrepancy_is_reported(self):
        write(self.source, [self.one])
        changed = self.one.copy()
        changed[4:] = ["110", "70", "40"]
        write(self.database, [changed])
        result = reconcile(self.source, self.database)
        self.assertEqual(result["status"], "mismatch")
        self.assertEqual(len(result["amount_mismatches"]), 1)

    def test_duplicate_keys_block_reconciliation(self):
        write(self.source, [self.one, self.one])
        write(self.database, [self.one])
        result = reconcile(self.source, self.database)
        self.assertEqual(result["status"], "invalid_input")

    def test_bad_profit_arithmetic_blocks_reconciliation(self):
        invalid = self.one.copy()
        invalid[-1] = "99"
        write(self.source, [invalid])
        write(self.database, [self.one])
        self.assertEqual(reconcile(self.source, self.database)["status"], "invalid_input")

    def test_non_finite_amount_blocks_reconciliation(self):
        invalid = self.one.copy()
        invalid[4] = "NaN"
        write(self.source, [invalid])
        write(self.database, [self.one])
        self.assertEqual(reconcile(self.source, self.database)["status"], "invalid_input")


if __name__ == "__main__":
    unittest.main()
