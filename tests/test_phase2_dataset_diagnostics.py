"""Tests for the opt-in process RSS diagnostic helper without importing the web app."""
import ast
import unittest
from pathlib import Path
from unittest.mock import mock_open, patch


def load_rss_helper():
    source = Path("app/server.py").read_text(encoding="utf-8")
    module = ast.parse(source, filename="app/server.py")
    function = next(
        node for node in module.body
        if isinstance(node, ast.FunctionDef) and node.name == "_rss_mb"
    )
    isolated = ast.Module(body=[function], type_ignores=[])
    namespace = {}
    exec(compile(isolated, "app/server.py", "exec"), namespace)
    return namespace["_rss_mb"]


_rss_mb = load_rss_helper()


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
