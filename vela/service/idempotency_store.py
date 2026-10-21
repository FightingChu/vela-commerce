"""幂等存储。#VT-2101 定义的"正经幂等表(带 TTL)"的进程内版,
下单/退款域里 remark 标记的方案统一收口到这里。

局限要清楚:
- 多实例不共享,只能挡网关重试风暴,挡不住跨实例并发;
- 进程重启即失效,所以下游仍要靠唯一键兜底。

DB 版落地后本模块换实现,接口不动。
"""

from __future__ import annotations

import datetime as dt
import threading

from vela.config.clocks import utc_now
from vela.config.logging import get_logger
from vela.domain.shared import build_key, normalize_token

log = get_logger(__name__)

DEFAULT_TTL_SECONDS = 600


def _read_clock(clock):
    """clock 收可调用或带 .now() 的对象(clocks.FrozenClock 是后者)。"""
    if clock is None:
        return utc_now
    return clock if callable(clock) else clock.now


class IdempotencyStore:
    """进程内 TTL KV。value 原样存(通常是首次响应的 dict)。"""

    def __init__(self, *, ttl_seconds: int = DEFAULT_TTL_SECONDS, clock=None):
        self._ttl = ttl_seconds
        self._clock = _read_clock(clock)
        self._data: dict[str, tuple[object, dt.datetime]] = {}
        self._lock = threading.Lock()

    def _prune(self, now: dt.datetime) -> None:
        expired = [k for k, (_, at) in self._data.items() if at <= now]
        for key in expired:
            del self._data[key]

    def get(self, key: str):
        with self._lock:
            self._prune(self._clock())
            entry = self._data.get(key)
            return entry[0] if entry is not None else None

    def put(self, key: str, payload, *, ttl_seconds: int | None = None) -> None:
        ttl = ttl_seconds if ttl_seconds is not None else self._ttl
        with self._lock:
            self._data[key] = (payload, self._clock() + dt.timedelta(seconds=ttl))

    def reserve(self, key: str, payload) -> bool:
        """占坑:第一次返回 True,重复返回 False(payload 不覆盖)。"""
        with self._lock:
            now = self._clock()
            self._prune(now)
            if key in self._data:
                return False
            self._data[key] = (payload, now + dt.timedelta(seconds=self._ttl))
            return True

    def clear(self) -> None:
        with self._lock:
            self._data.clear()


#: 进程级单例。测试里用 clear() 或直接 new 一个,别 patch 这个变量
_global_store = IdempotencyStore()


def get_global_store() -> IdempotencyStore:
    return _global_store


def check_and_mark(scope: str, token, payload=None) -> tuple[bool, object]:
    """scope:token 组合查重。返回 (是否首次, 已有结果)。

    token 为空(含老网关 "-1")不拦截,直接放行并返回首抢成功——
    和 order/settlement 域"没 token 跳过幂等"的行为保持一致。
    """
    token = normalize_token(token)
    if not token:
        return True, None
    key = build_key(scope, token)
    existing = _global_store.get(key)
    if existing is not None:
        log.info("idempotency_hit", scope=scope, key=key)
        return False, existing
    _global_store.put(key, payload)
    return True, None
