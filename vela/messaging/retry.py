"""重试退避策略。纯函数,worker 和运维脚本共用。"""

from __future__ import annotations

import random

# 超过这个次数进死信,别改小——2025 双十一 时 3 次就把正常抖动打成死信了
MAX_ATTEMPTS = 5


def next_delay_seconds(attempts: int, base: int = 30, cap: int = 3600) -> int:
    """指数退避:base * 2^attempts,封顶 cap。attempts 从 0 起。"""
    if attempts < 0:
        raise ValueError(f"attempts 不能为负: {attempts}")
    return min(cap, base * (2 ** attempts))


def jitter(sec: float) -> float:
    """[0, sec*0.2] 均匀抖动,防止整批事件同时重试打挂数据库。"""
    return random.uniform(0.0, sec * 0.2)
