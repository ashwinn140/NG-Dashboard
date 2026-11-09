"""Register Volume is reported in cubic metres: CCM (cubic centimetre) rows are converted."""
import unittest
import pandas as pd
from app import dataset as D


class VolumeUnitTests(unittest.TestCase):
    def frame(self, vols, units, col="Unit.5"):
        # The register repeats "Unit" (weight KGS, packages PKG, ...); only one column holds the volume unit.
        return pd.DataFrame({"Volume": vols, "Unit": ["KGS"] * len(vols), "Unit.3": ["PKG"] * len(vols), col: units})

    def test_cbm_rows_unchanged_and_ccm_rows_divided_by_a_million(self):
        out = D.volume_cbm(self.frame([2.0, 15809420, 5], ["CBM", "CCM", "CBM"])).tolist()
        self.assertEqual(out[0], 2.0)
        self.assertAlmostEqual(out[1], 15.80942)
        self.assertEqual(out[2], 5.0)

    def test_unit_position_does_not_matter(self):
        for col in ("Unit.4", "Unit.5", "Unit.7"):
            with self.subTest(col=col):
                self.assertAlmostEqual(D.volume_cbm(self.frame([1_000_000], ["CCM"], col)).iloc[0], 1.0)

    def test_case_and_spacing_are_ignored(self):
        self.assertAlmostEqual(D.volume_cbm(self.frame([500000], [" ccm "])).iloc[0], 0.5)

    def test_blank_unit_and_bad_volume_are_safe(self):
        out = D.volume_cbm(self.frame([3.0, "x", None], ["", "CCM", None])).tolist()
        self.assertEqual(out, [3.0, 0.0, 0.0])

    def test_other_unit_columns_never_trigger_conversion(self):
        A = pd.DataFrame({"Volume": [7.0], "Unit": ["KGS"], "Unit.1": ["PKG"], "Unit.2": ["NOS"]})
        self.assertEqual(D.volume_cbm(A).tolist(), [7.0])

    def test_missing_volume_column_gives_zeros(self):
        self.assertEqual(D.volume_cbm(pd.DataFrame({"Unit": ["CBM", "CCM"]})).tolist(), [0.0, 0.0])

    def test_unit_columns_are_loaded_by_the_dataset_query(self):
        for c in ("Unit", "Unit.1", "Unit.7"):
            self.assertIn(c, D.DASHBOARD_COLUMNS)


if __name__ == "__main__":
    unittest.main()
