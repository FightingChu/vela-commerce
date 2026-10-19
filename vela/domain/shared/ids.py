"""业务标识生成。订单号/退款号/结算单号格式:前缀 + yyMMdd + 序列。

线上是多实例,序列段用的是每实例一段,重启会跳号,业务上可接受。
"""

from __future__ import annotations

import datetime as dt
import itertools
import random
import threading


class SerialGenerator:
    """进程内自增,带锁。序列段 6 位,到顶归零(单机 QPS 到不了)。"""

    def __init__(self, start: int | None = None, *, width: int = 6):
        self._counter = itertools.count(start if start is not None else random.randint(1, 500))
        self._lock = threading.Lock()
        self._width = width

    def next_serial(self) -> int:
        with self._lock:
            n = next(self._counter)
        return n % (10**self._width)

    def next_padded(self) -> str:
        return str(self.next_serial()).zfill(self._width)


def date_segment(now: dt.datetime | None = None) -> str:
    now = now or dt.datetime.now(tz=dt.timezone.utc)
    return now.strftime("%y%m%d")


def build_sn(prefix: str, serial: str | int, *, now: dt.datetime | None = None) -> str:
    if not prefix or not prefix.isalpha():
        raise ValueError(f"非法单号前缀: {prefix!r}")
    serial_str = str(serial).zfill(6)[-6:] if not isinstance(serial, int) else str(serial % 10**6).zfill(6)
    return f"{prefix}{date_segment(now)}{serial_str}"


def order_sn(serial: str | int, *, now: dt.datetime | None = None) -> str:
    from vela.config.constants import ORDER_SN_PREFIX

    return build_sn(ORDER_SN_PREFIX, serial, now=now)


def refund_sn(serial: str | int, *, now: dt.datetime | None = None) -> str:
    from vela.config.constants import REFUND_SN_PREFIX

    return build_sn(REFUND_SN_PREFIX, serial, now=now)


def settlement_sn(serial: str | int, *, now: dt.datetime | None = None) -> str:
    from vela.config.constants import SETTLEMENT_SN_PREFIX

    return build_sn(SETTLEMENT_SN_PREFIX, serial, now=now)


def trace_id() -> str:
    """16 进制伪随机,只用于日志串联,不做安全用途。"""
    return f"t-{random.getrandbits(64):016x}"
