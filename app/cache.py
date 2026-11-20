"""Small byte-bounded LRU cache for already-encoded dashboard payloads.

The cache stores immutable bytes only. It deliberately knows nothing about users,
permissions, or dataset versions: callers must continue to use the full security
scope in their cache key.
"""
from collections import OrderedDict


class ByteBoundedLRU:
    """An insertion-ordered LRU with both byte and entry ceilings."""

    def __init__(self, max_bytes: int = 64 * 1024 * 1024, max_entries: int = 20):
        if max_bytes < 0:
            raise ValueError("max_bytes must be non-negative")
        if max_entries < 0:
            raise ValueError("max_entries must be non-negative")
        self.max_bytes = int(max_bytes)
        self.max_entries = int(max_entries)
        self._items = OrderedDict()
        self.current_bytes = 0

    def __len__(self):
        return len(self._items)

    def __contains__(self, key):
        return key in self._items

    def get(self, key, default=None):
        item = self._items.get(key)
        if item is None:
            return default
        self._items.move_to_end(key)
        return item

    def __getitem__(self, key):
        try:
            value = self._items[key]
        except KeyError:
            raise
        self._items.move_to_end(key)
        return value

    def __setitem__(self, key, value):
        if not isinstance(value, bytes):
            raise TypeError("cache values must be bytes")
        self.pop(key, None)
        size = len(value)
        # Oversized entries are returned to the caller but never retained.
        if not self.max_entries or not self.max_bytes or size > self.max_bytes:
            return
        self._items[key] = value
        self.current_bytes += size
        while self._items and (
            len(self._items) > self.max_entries
            or self.current_bytes > self.max_bytes
        ):
            _, evicted = self._items.popitem(last=False)
            self.current_bytes -= len(evicted)

    def pop(self, key, default=None):
        value = self._items.pop(key, default)
        if value is not default:
            self.current_bytes -= len(value)
        return value

    def clear(self):
        self._items.clear()
        self.current_bytes = 0
