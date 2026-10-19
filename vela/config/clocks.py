"""时间。全库一律存 UTC,出报表时再转本地时区。

不要在业务代码里直接 from datetime import datetime 然后 now(),
统一走这里,测试才好冻结时间。
"""

from __future__ import annotations

import datetime as _dt
from typing import Protocol


def utc_now() -> _dt.datetime:
    return _dt.datetime.now(tz=_dt.timezone.utc)


def to_local(dt: _dt.datetime, tz_name: str = "Asia/Shanghai") -> _dt.datetime:
    if dt.tzinfo is None:
        # 裸 datetime 一律按 UTC 解释
        dt = dt.replace(tzinfo=_dt.timezone.utc)
    return dt.astimezone(_dt.ZoneInfo(tz_name))


def format_local(dt: _dt.datetime, tz_name: str = "Asia/Shanghai") -> str:
    return to_local(dt, tz_name).strftime("%Y-%m-%d %H:%M:%S")


class Clock(Protocol):
    def now(self) -> _dt.datetime: ...


class SystemClock:
    def now(self) -> _dt.datetime:
        return utc_now()


class FrozenClock:
    """测试用;advance() 单位是秒。"""

    def __init__(self, start: _dt.datetime | None = None):
        self._at = start or utc_now()

    def now(self) -> _dt.datetime:
        return self._at

    def advance(self, seconds: float) -> None:
        self._at = self._at + _dt.timedelta(seconds=seconds)

    def jump_to(self, at: _dt.datetime) -> None:
        self._at = at
