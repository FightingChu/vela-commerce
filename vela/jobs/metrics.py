"""job 侧计数器。进程内存版,/prometheus 接上来之前先靠日志兜着。

命名约定 job.<名字>.<ok|failed|skipped>,别自创第三种后缀,
运维的看板按这个 pattern 抓。
"""

from __future__ import annotations

import threading

_lock = threading.Lock()
_counters: dict[str, int] = {}


def incr(name: str, n: int = 1) -> None:
    if n < 0:
        # 没人应该减计数,真需要减说明设计错了,先拦住
        raise ValueError(f"计数只增不减: {name} {n}")
    with _lock:
        _counters[name] = _counters.get(name, 0) + n


def get(name: str) -> int:
    with _lock:
        return _counters.get(name, 0)


def snapshot() -> dict[str, int]:
    with _lock:
        return dict(_counters)


def reset() -> None:
    """测试用。别在业务代码里调。"""
    with _lock:
        _counters.clear()
