"""Read-only historical archive audit safety tests."""
import tempfile
import unittest
from pathlib import Path
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

    @patch("scripts.audit_historical_profit.is_profit_report", return_value=False)
    def test_unrelated_workbook_is_not_reported(self, _):
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory) / "unrelated.xlsx").write_bytes(b"unrelated")
            result = inspect(Path(directory), 2024)
        self.assertEqual(result["files_inspected"], 0)


if __name__ == "__main__":
    unittest.main()
