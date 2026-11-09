"""Read-only historical archive audit safety tests."""
import tempfile
import unittest
from pathlib import Path
from datetime import date
from types import SimpleNamespace

import pandas as pd
from unittest.mock import patch

from scripts.audit_historical_profit import _hash_file, inspect


class HistoricalProfitAuditTests(unittest.TestCase):
    def test_empty_archive_has_no_eligible_files(self):
        with tempfile.TemporaryDirectory() as directory:
            result = inspect(Path(directory), 2024)
        self.assertEqual(result["files_inspected"], 0)
        self.assertEqual(result["eligible"], 0)
        self.assertIn("does not", result["warning"])

    def test_non_excel_files_are_ignored(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "report.txt"
            path.write_text("not an excel workbook", encoding="utf-8")
            result = inspect(Path(directory), 2024)
        self.assertEqual(result["files_inspected"], 0)

    def test_hash_is_stable(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "source.xlsx"
            path.write_bytes(b"test archive bytes")
            self.assertEqual(_hash_file(path), _hash_file(path))

    @patch("scripts.audit_historical_profit.validate_profit", return_value=[])
    @patch("scripts.audit_historical_profit.read_profit")
    @patch("scripts.audit_historical_profit.is_profit_report", return_value=True)
    def test_cross_year_report_splits_requested_year_totals(self, _, reader, __):
        reader.return_value = SimpleNamespace(
            company="NG", basis="Job Date",
            range_from=date(2023, 12, 1), range_to=date(2024, 1, 31),
            df=pd.DataFrame({
                "Job Date": [date(2023, 12, 20), date(2024, 1, 10)],
                "Income (INR)": [100, 250],
                "Expense (INR)": [40, 80],
                "Profit (INR)": [60, 170],
            }))
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory) / "source.xlsx").write_bytes(b"sample")
            result = inspect(Path(directory), 2024)
        self.assertEqual(result["files_inspected"], 1)
        row = result["files"][0]
        self.assertEqual(row["jobs"], 2)
        self.assertEqual(row["jobs_in_requested_year"], 1)
        self.assertEqual(row["totals"]["Income (INR)"], 350)
        self.assertEqual(row["totals_in_requested_year"]["Income (INR)"], 250)
        self.assertTrue(row["requires_period_split"])

    @patch("scripts.audit_historical_profit.is_profit_report", return_value=False)
    def test_unrelated_workbook_is_not_reported(self, _):
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory) / "unrelated.xlsx").write_bytes(b"unrelated")
            result = inspect(Path(directory), 2024)
        self.assertEqual(result["files_inspected"], 0)


if __name__ == "__main__":
    unittest.main()
