"""简单令牌桶,消费侧限流用。

背景:大促时下游回调被打爆过一次(#VT-1963),加了这层。
没有做分布式版,多进程各自限各自的,够用。
"""

from __future__ import annotations

import asyncio
import time


class TokenBucket:

    def __init__(self, capacity: float, refill_per_sec: float):
        if capacity <= 0 or refill_per_sec < 0:
            raise ValueError("capacity 必须 > 0,refill_per_sec 必须 >= 0")
        self.capacity = float(capacity)
        self.refill_per_sec = float(refill_per_sec)
        self._tokens = float(capacity)
        self._last = time.monotonic()

    def _refill(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last
        if elapsed > 0:
            self._tokens = min(self.capacity, self._tokens + elapsed * self.refill_per_sec)
            self._last = now

    def try_take(self, n: int = 1) -> bool:
        self._refill()
        if self._tokens >= n:
            self._tokens -= n
            return True
        return False

    @property
    def tokens(self) -> float:
        self._refill()
        return self._tokens


class AsyncTokenBucket:
    """asyncio 版,加锁防止并发 try_take 时多扣。"""

    def __init__(self, capacity: float, refill_per_sec: float):
        if capacity <= 0 or refill_per_sec < 0:
            raise ValueError("capacity 必须 > 0,refill_per_sec 必须 >= 0")
        self.capacity = float(capacity)
        self.refill_per_sec = float(refill_per_sec)
        self._tokens = float(capacity)
        self._last = time.monotonic()
        self._lock = asyncio.Lock()

    def _refill_unlocked(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last
        if elapsed > 0:
            self._tokens = min(self.capacity, self._tokens + elapsed * self.refill_per_sec)
            self._last = now

    async def try_take(self, n: int = 1) -> bool:
        async with self._lock:
            self._refill_unlocked()
            if self._tokens >= n:
                self._tokens -= n
                return True
            return False

    async def tokens(self) -> float:
        async with self._lock:
            self._refill_unlocked()
            return self._tokens
