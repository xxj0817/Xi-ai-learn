"""轻量内存限流器，避免 MVP 阶段引入额外中间件依赖。"""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque

from app.core.exceptions import RateLimited


class RateLimiter:
    def __init__(self, limit: int, window_seconds: float = 60.0) -> None:
        self._limit = limit
        self._window = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, key: str) -> None:
        now = time.monotonic()
        with self._lock:
            hits = self._hits[key]
            while hits and now - hits[0] > self._window:
                hits.popleft()
            if len(hits) >= self._limit:
                raise RateLimited()
            hits.append(now)
