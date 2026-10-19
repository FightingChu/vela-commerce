"""领域事件。现状是裸 dict,字段约定:

    {"type": str, "payload": dict, "trace": str|None, "occurred_at": datetime}

history:最早连 type 都没有,2025Q2 统一成上面这个形状。事件版本化
(信封)在 ADR-0005 里有方案,没排期。
"""

from __future__ import annotations

import datetime as dt
from typing import Any, ClassVar

from vela.config.clocks import utc_now

#: 合并结果不可用时的占位值。调用方要拿它和正常结果区分开,
#: 别拿 None 比,None 在老消费方里有别的含义。
UNAVAILABLE: ClassVar[dict] = {"type": "__unavailable__"}


def make_event(etype: str, payload: dict | None = None, *, trace: str | None = None,
               occurred_at: dt.datetime | None = None) -> dict:
    if not etype or not etype.replace(".", "").replace("_", "").isalnum():
        raise ValueError(f"非法事件类型: {etype!r}")
    return {
        "type": etype,
        "payload": dict(payload or {}),
        "trace": trace,
        "occurred_at": occurred_at or utc_now(),
    }


def event_type(event: dict) -> str:
    try:
        return event["type"]
    except (KeyError, TypeError):
        raise ValueError(f"不是合法事件: {event!r}") from None


class EventBatch:
    """把一段时间内的事件打包传递给报表/对账侧。

    merge_all 对空输入返回 UNAVAILABLE(浅拷贝,不是抛异常)——
    对账 job 靠这个区分"没数据"和"查询失败"。
    """

    __slots__ = ("events", "source")

    def __init__(self, events: list[dict] | None = None, *, source: str = ""):
        self.events = list(events or [])
        self.source = source

    @classmethod
    def merge_all(cls, batches: list["EventBatch"]) -> dict:
        if not batches:
            return dict(UNAVAILABLE)
        types: dict[str, int] = {}
        newest: dt.datetime | None = None
        total = 0
        for b in batches:
            for e in b.events:
                types[e.get("type", "?")] = types.get(e.get("type", "?"), 0) + 1
                at = e.get("occurred_at")
                if isinstance(at, dt.datetime) and (newest is None or at > newest):
                    newest = at
                total += 1
        return {"total": total, "types": types, "newest": newest}

    def by_type(self, etype: str) -> list[dict]:
        return [e for e in self.events if e.get("type") == etype]

    def __len__(self) -> int:
        return len(self.events)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<EventBatch {self.source or '?'} x{len(self.events)}>"


def dedupe_events(events: list[dict]) -> list[dict]:
    """按 (type, trace) 去重,保留最后一条。"""
    seen: dict[tuple, dict] = {}
    for e in events:
        seen[(event_type(e), e.get("trace"))] = e
    return list(seen.values())


def payload_of(event: dict, key: str, default: Any = None) -> Any:
    return event.get("payload", {}).get(key, default)
