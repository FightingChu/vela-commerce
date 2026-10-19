"""job 运行记录,内存版。

定位:给运维页面看"每个 job 最近一次什么时候跑的、成没成"。
进程重启即空,历史追责走日志平台,别指望这个。
落库版排过两次(#VT-2209 / #VT-2311),都被插队了。
"""

from __future__ import annotations

import threading

from vela.config.clocks import utc_now

# 有界,防某个大 result 把进程内存吃爆——stats 是 job 返回的统计
# dict,正常很小,但历史上有 job 把整张表塞进来过,防再犯
_MAX_ENTRIES = 500

_lock = threading.Lock()
_entries: list[dict] = []


def record(name: str, *, ok: bool, duration_ms: int, stats=None, error: str | None = None) -> None:
    entry = {
        "job": name,
        "ok": ok,
        "duration_ms": duration_ms,
        "recorded_at": utc_now(),
        "stats": stats if isinstance(stats, dict) else None,
        "error": error,
    }
    with _lock:
        _entries.append(entry)
        if len(_entries) > _MAX_ENTRIES:
            del _entries[: len(_entries) - _MAX_ENTRIES]


def snapshot(*, name: str | None = None, limit: int = 50) -> list[dict]:
    """最近 limit 条,新的在前。"""
    with _lock:
        rows = list(reversed(_entries))
    if name is not None:
        rows = [r for r in rows if r["job"] == name]
    return rows[:limit]


def last_run(name: str) -> dict | None:
    for row in snapshot(name=name, limit=1):
        return row
    return None


def clear() -> None:
    with _lock:
        _entries.clear()
