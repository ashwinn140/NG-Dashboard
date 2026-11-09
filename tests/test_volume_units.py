"""Register Volume conversion uses only the unit paired with the Volume field."""
import unittest
import pandas as pd
from app import dataset as D, processor as P


class VolumeUnitTests(unittest.TestCase):
    def test_volume_unit_field_controls_conversion(self):
        A = pd.DataFrame({"Volume": [2.0, 1_000_000, 500_000],
                          "_volume_unit_source": ["CBM", "CCM", " ccm "],
                          "Unit": ["CCM", "KGS", "PKG"], "Unit.1": ["CCM", "NOS", "KGS"],
                          "Unit.5": ["CCM", "CBM", "CBM"]})
        out = D.volume_cbm(A).tolist()
        self.assertEqual(out[0], 2.0)
        self.assertEqual(out[1], 1.0)
        self.assertEqual(out[2], 0.5)

    def test_legacy_rows_use_only_audited_volume_unit_column(self):
        A = pd.DataFrame({"Volume": [1_000_000, 1_000_000], "Unit": ["CCM", "KGS"],
                          "Unit.1": ["CCM", "PKG"], "Unit.5": ["CBM", "CCM"]})
        self.assertEqual(D.volume_cbm(A).tolist(), [1_000_000, 1.0])

    def test_new_import_maps_unit_immediately_after_volume_by_source_order(self):
        df = pd.DataFrame([{"Shipment No": "S1", "Shipment Date": "2026-11-01",
            "Branch": "Mumbai", "Customer": "Alpha", "Status": "Open", "Job Owner": "Owner",
            "Volume": "1000000", "Unit.5": "CCM", "Unit.1": "KGS"}],
            columns=["Shipment No", "Shipment Date", "Branch", "Customer", "Status",
                     "Job Owner", "Volume", "Unit.5", "Unit.1"])
        row = P.standardise(P.Register("NG", "AE", df, "test"))[0]
        self.assertEqual(row["extra"]["_volume_unit_source"], "CCM")

    def test_new_import_does_not_fallback_when_no_adjacent_unit(self):
        df = pd.DataFrame([{"Shipment No": "S2", "Shipment Date": "2026-11-01",
            "Branch": "Mumbai", "Customer": "Alpha", "Status": "Open", "Job Owner": "Owner",
            "Volume": "1000000", "Description": "Goods", "Unit.5": "CCM"}],
            columns=["Shipment No", "Shipment Date", "Branch", "Customer", "Status",
                     "Job Owner", "Volume", "Description", "Unit.5"])
        row = P.standardise(P.Register("NG", "AE", df, "test"))[0]
        self.assertEqual(row["extra"]["_volume_unit_source"], "__NO_ADJACENT_UNIT__")

    def test_other_unit_columns_never_trigger_conversion(self):
        A = pd.DataFrame({"Volume": [7.0], "Unit": ["CCM"], "Unit.1": ["CCM"],
                          "Unit.2": ["CCM"], "Unit.3": ["CCM"], "Unit.4": ["CCM"],
                          "Unit.5": ["CBM"], "Unit.6": ["CCM"], "Unit.7": ["CCM"]})
        self.assertEqual(D.volume_cbm(A).tolist(), [7.0])

    def test_case_and_spacing_are_ignored(self):
        self.assertEqual(D.volume_cbm(pd.DataFrame({"Volume": [500000],
            "_volume_unit_source": [" ccm "]})).tolist(), [0.5])

    def test_blank_unit_and_bad_volume_are_safe(self):
        A = pd.DataFrame({"Volume": [3.0, "x", None],
                          "_volume_unit_source": ["", "CCM", None]})
        self.assertEqual(D.volume_cbm(A).tolist(), [3.0, 0.0, 0.0])

    def test_missing_volume_column_gives_zeros(self):
        self.assertEqual(D.volume_cbm(pd.DataFrame({"Unit.5": ["CBM", "CCM"]})).tolist(), [0.0, 0.0])

    def test_private_unit_mapping_is_loaded_by_dataset_query(self):
        self.assertIn("_volume_unit_source", D.DASHBOARD_COLUMNS)


if __name__ == "__main__":
    unittest.main()
