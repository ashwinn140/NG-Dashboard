"""Tests for the opt-in process RSS diagnostic helper."""
import unittest
from unittest.mock import mock_open, patch

from app.server import _rss_mb


class DatasetDiagnosticsTests(unittest.TestCase):
    def test_reads_resident_memory_from_proc_status(self):
        status = "Name:\tpython\nVmPeak:\t20000 kB\nVmRSS:\t12345 kB\n"
        with patch("builtins.open", mock_open(read_data=status)):
            self.assertEqual(_rss_mb(), 12.1)

    def test_returns_none_when_proc_status_is_unavailable(self):
        with patch("builtins.open", side_effect=OSError("procfs unavailable")):
            self.assertIsNone(_rss_mb())

    def test_returns_none_when_rss_field_is_missing(self):
        with patch("builtins.open", mock_open(read_data="Name:\tpython\nVmPeak:\t20000 kB\n")):
            self.assertIsNone(_rss_mb())


if __name__ == "__main__":
    unittest.main()
