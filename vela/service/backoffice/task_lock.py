"""后台锁。进程内 TTL 互斥,给 backoffice 任务(导出/批量调整)防
手工触发撞定时轮。

和 jobs/locks.py 是两份实现——那份是 job 调度域的,这边是后台任务域
的,2025 年合并讨论过,因为过期语义不同(那边要静默跳过,这边要
显式报错)没合。跨进程互斥都挡不住,靠 DB 状态机兜,#VT-2190。
"""

from __future__ import annotations

import contextlib
import datetime as dt
import threading

from vela.config.clocks import utc_now
from vela.config.errors import ConflictError

DEFAULT_TTL_SECONDS = 600


def _read_clock(clock):
    """clock 收可调用或带 .now() 的对象(clocks.FrozenClock 是后者)。"""
    if clock is None:
        return utc_now
    return clock if callable(clock) else clock.now


class LockHeldError(ConflictError):
    """锁被占。http_status 沿用 ConflictError 的 409。"""

    code = "vela.0411"


class TaskLock:
    """名字 -> (owner, 过期时间) 的进程内注册表。

    ttl 是防某次执行卡死后锁永不释放;过期后别的 owner 可以抢,
    原 owner 再 release 是 no-op(不报错,幂等语义对后台任务友好)。
    """

    def __init__(self, *, ttl_seconds: int = DEFAULT_TTL_SECONDS, clock=None):
        self._ttl = ttl_seconds
        self._clock = _read_clock(clock)
        self._held: dict[str, tuple[str, dt.datetime]] = {}
        self._mu = threading.Lock()

    def acquire(self, name: str, *, owner: str = "") -> bool:
        now = self._clock()
        with self._mu:
            entry = self._held.get(name)
            if entry is not None:
                _, expires_at = entry
                if expires_at > now:
                    return False
                # 过期锁,顶掉
                del self._held[name]
            self._held[name] = (owner, now + dt.timedelta(seconds=self._ttl))
            return True

    def release(self, name: str, *, owner: str = "") -> bool:
        """只有持锁人能放。返回是否真的释放了一把锁。"""
        with self._mu:
            entry = self._held.get(name)
            if entry is None or entry[0] != owner:
                return False
            del self._held[name]
            return True

    def holder(self, name: str) -> str | None:
        """当前持锁人(没过期才有)。诊断用。"""
        now = self._clock()
        with self._mu:
            entry = self._held.get(name)
            if entry is None or entry[1] <= now:
                return None
            return entry[0]


@contextlib.contextmanager
def hold(lock: TaskLock, name: str, *, owner: str = ""):
    """占锁执行,占不到抛 LockHeldError(调用方决定提示语)。

    with hold(task_lock, "export:orders:main"): ...
    """
    if not lock.acquire(name, owner=owner):
        raise LockHeldError(
            f"任务锁被占: {name}", detail={"name": name, "holder": lock.holder(name)}
        )
    try:
        yield name
    finally:
        lock.release(name, owner=owner)
