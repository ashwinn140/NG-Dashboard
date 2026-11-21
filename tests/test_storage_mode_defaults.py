import unittest
from unittest.mock import patch

from app import config


class StorageModeDefaultsTests(unittest.TestCase):
    def test_versioned_mode_keeps_legacy_non_static_default(self):
        with patch.dict("os.environ", {"REPORT_STORAGE_MODE": "versioned"}, clear=False):
            with patch.dict("os.environ", {}, clear=False):
                # Remove the optional override for this assertion.
                import os
                os.environ.pop("REPORT_STATIC_HISTORY", None)
                self.assertFalse(config.static_history())

    def test_replace_mode_defaults_to_historical_freeze(self):
        import os
        with patch.dict("os.environ", {"REPORT_STORAGE_MODE": "replace"}, clear=False):
            os.environ.pop("REPORT_STATIC_HISTORY", None)
            self.assertTrue(config.static_history())

    def test_explicit_history_override_is_respected(self):
        with patch.dict("os.environ", {"REPORT_STORAGE_MODE": "replace", "REPORT_STATIC_HISTORY": "0"}, clear=False):
            self.assertFalse(config.static_history())


if __name__ == "__main__":
    unittest.main()
