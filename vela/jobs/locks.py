"""防并发重入,进程内存版。

同一台机器上调度器不会并发触发同名 job(APScheduler max_instances=1
兜着),这层防的是:手工触发撞上 cron、两个 job 进程共享内存误判、
以及 run_all_once 撞上正在跑的定时轮。

多实例部署时这里挡不住跨进程重入,靠 DB 行锁/状态机兜底。
Redis 版在 #VT-2190,排期没定,先别在关键路径上依赖它。
"""

from __future__ import annotations

import threading
import time

# 锁的自动过期。正常任务几十秒内完事,给 10 分钟是防某次执行
# 卡死后锁永远不释放(内存版没有可靠的崩溃清理)。
DEFAULT_TTL_SECONDS = 600

# 名字 -> 过期时刻(monotonic)。_HOLD 单独一个锁保护,读写都短,
# 不值得上读写锁。
_HOLD: dict[str, float] = {}
_lock = threading.Lock()


def try_hold(name: str, ttl_seconds: int = DEFAULT_TTL_SECONDS) -> bool:
    """抢到返回 True。已有未过期的持有者时返回 False。"""
    now = time.monotonic()
    with _lock:
        expire_at = _HOLD.get(name)
        if expire_at is not None and expire_at > now:
            return False
        _HOLD[name] = now + ttl_seconds
        return True


def release(name: str) -> None:
    """没有也照放,调用方不用判。"""
    with _lock:
        _HOLD.pop(name, None)


def held(name: str) -> bool:
    """查询用(调试/运维页面),不做抢锁语义。"""
    now = time.monotonic()
    with _lock:
        expire_at = _HOLD.get(name)
    return expire_at is not None and expire_at > now


def reset() -> None:
    """测试用,业务代码别碰。"""
    with _lock:
        _HOLD.clear()
