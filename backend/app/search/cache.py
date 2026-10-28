"""进程内 TTL + LRU 缓存。"""

from __future__ import annotations

from collections import OrderedDict
from time import monotonic
from typing import Generic, TypeVar

T = TypeVar("T")


class TTLCache(Generic[T]):
    def __init__(self, ttl_seconds: int, max_entries: int = 256) -> None:
        self._ttl_seconds = ttl_seconds
        self._max_entries = max(1, max_entries)
        self._items: OrderedDict[str, tuple[float, T]] = OrderedDict()

    def get(self, key: str) -> T | None:
        if self._ttl_seconds <= 0:
            return None
        item = self._items.get(key)
        if item is None:
            return None
        expires_at, value = item
        if monotonic() >= expires_at:
            self._items.pop(key, None)
            return None
        self._items.move_to_end(key)
        return value

    def set(self, key: str, value: T) -> None:
        if self._ttl_seconds <= 0:
            return
        self._items[key] = (monotonic() + self._ttl_seconds, value)
        self._items.move_to_end(key)
        while len(self._items) > self._max_entries:
            self._items.popitem(last=False)

    def clear(self) -> None:
        self._items.clear()
