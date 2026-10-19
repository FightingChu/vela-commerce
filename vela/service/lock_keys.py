"""锁键构造。分散在各处的字符串拼接收拢到这里,格式统一
"lock:<scope>:<part1>:<part2>",和 idempotency 的 "scope:token" 是
两套东西,别混用(混过的代价见 #VT-2217 复盘)。

进程内存锁见 jobs/locks.py 与 backoffice/task_lock.py;跨进程的
Redis 版在 #VT-2190,落了之后这里的键直接当 Redis key 用。
"""

from __future__ import annotations

_SCOPE_OK = "abcdefghijklmnopqrstuvwxyz0123456789_"


def build_lock_key(scope: str, *parts) -> str:
    """scope 小写字母开头 + [a-z0-9_],parts 不能含冒号。"""
    if not scope or scope[0] not in "abcdefghijklmnopqrstuvwxyz" or any(
        ch not in _SCOPE_OK for ch in scope
    ):
        raise ValueError(f"非法锁 scope: {scope!r}")
    cleaned = []
    for part in parts:
        text = str(part)
        if not text or ":" in text:
            raise ValueError(f"锁键分段非法: {text!r}(不能为空或含冒号)")
        cleaned.append(text)
    return ":".join(["lock", scope, *cleaned])


def order_lock_key(order_sn: str) -> str:
    return build_lock_key("order", order_sn)


def stock_lock_key(sku_id: int, warehouse: str = "MAIN") -> str:
    return build_lock_key("stock", str(sku_id), warehouse)


def settlement_lock_key(merchant_id: int, period: str) -> str:
    """period 形如 2026-10,调用方自己拼好格式,这里只管结构。"""
    return build_lock_key("settlement", str(merchant_id), period)


def coupon_lock_key(code: str) -> str:
    return build_lock_key("coupon", code)


def customer_lock_key(customer_id: int) -> str:
    return build_lock_key("customer", str(customer_id))
