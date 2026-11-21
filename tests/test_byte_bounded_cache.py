import unittest

from app.cache import ByteBoundedLRU


class ByteBoundedLRUTests(unittest.TestCase):
    def test_evicts_least_recently_used_by_bytes(self):
        cache = ByteBoundedLRU(max_bytes=6, max_entries=10)
        cache["a"] = b"aaa"
        cache["b"] = b"bbb"
        self.assertEqual(cache.get("a"), b"aaa")  # a becomes most recently used
        cache["c"] = b"ccc"
        self.assertNotIn("b", cache)
        self.assertIn("a", cache)
        self.assertIn("c", cache)
        self.assertEqual(cache.current_bytes, 6)

    def test_entry_limit_and_replacement_accounting(self):
        cache = ByteBoundedLRU(max_bytes=100, max_entries=2)
        cache["a"] = b"one"
        cache["b"] = b"two"
        cache["a"] = b"longer"
        self.assertEqual(cache.current_bytes, 9)
        cache["c"] = b"x"
        self.assertNotIn("b", cache)
        self.assertIn("a", cache)
        self.assertEqual(cache.current_bytes, 7)

    def test_oversized_entry_is_not_retained(self):
        cache = ByteBoundedLRU(max_bytes=3, max_entries=2)
        cache["large"] = b"four"
        self.assertEqual(len(cache), 0)
        self.assertEqual(cache.current_bytes, 0)

    def test_clear_resets_byte_accounting(self):
        cache = ByteBoundedLRU(max_bytes=10, max_entries=3)
        cache["a"] = b"123"
        cache.clear()
        self.assertEqual(len(cache), 0)
        self.assertEqual(cache.current_bytes, 0)

    def test_pop_updates_accounting_and_missing_default(self):
        cache = ByteBoundedLRU(max_bytes=10, max_entries=3)
        cache["a"] = b"123"
        self.assertEqual(cache.pop("a"), b"123")
        self.assertEqual(cache.current_bytes, 0)
        self.assertIsNone(cache.pop("missing", None))
        with self.assertRaises(KeyError):
            cache.pop("missing")

    def test_rejects_non_bytes(self):
        cache = ByteBoundedLRU()
        with self.assertRaises(TypeError):
            cache["bad"] = "payload"


if __name__ == "__main__":
    unittest.main()
