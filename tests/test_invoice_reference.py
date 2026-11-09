"""Invoice-reference detection: empty placeholders must not count as invoiced."""
import unittest
import numpy as np
from app import dataset as D


class InvoiceReferenceTests(unittest.TestCase):
    def test_empty_and_zero_placeholders_are_not_invoices(self):
        for v in (None, np.nan, "", " ", "0", 0, 0.0, "0.0", "nan", "NaN", "-"):
            with self.subTest(v=v):
                self.assertEqual(D._inv(v, None), (-1, 0))
                self.assertEqual(D._inv(None, v), (-1, 0))

    def test_real_references_still_count(self):
        self.assertEqual(D._inv("INV123 dt. 12-Oct-2026", None), (20738, 1))
        day, n = D._inv("INV/24/001 dt 05 Oct 2026; INV/24/002 dt. 09-Oct-2026", None)
        self.assertEqual((day, n), (20731, 2))

    def test_reference_without_parseable_date_counts_but_has_no_date(self):
        self.assertEqual(D._inv("INV123", None), (-1, 1))
        self.assertEqual(D._inv("INV123 12-Oct-2026", None), (-1, 1))

    def test_either_field_can_carry_the_reference(self):
        self.assertEqual(D._inv(None, "INV9 dt. 01-Nov-2026")[1], 1)
        self.assertEqual(D._inv("0", "INV9 dt. 01-Nov-2026")[1], 1)

    def test_na_nil_pending_placeholders_are_not_invoices(self):
        # Product-owner decision (9 Nov 2026): N/A, NIL and Pending mean "no invoice".
        for v in ("N/A", "n/a", "NA", "N.A.", "NIL", "nil", "Nil.", "Pending", "PENDING", " pending "):
            with self.subTest(v=v):
                self.assertEqual(D._inv(v, None), (-1, 0))
                self.assertEqual(D._inv(None, v), (-1, 0))

    def test_placeholder_words_with_digits_or_inside_references_still_count(self):
        for v in ("NIL 123", "Pending 55", "INVNA", "INV9 dt. 01-Nov-2026"):
            with self.subTest(v=v):
                self.assertEqual(D._inv(v, None)[1], 1)

    def test_placeholder_in_one_field_does_not_hide_a_reference_in_the_other(self):
        self.assertEqual(D._inv("N/A", "INV9 dt. 01-Nov-2026"), (20758, 1))


if __name__ == "__main__":
    unittest.main()
