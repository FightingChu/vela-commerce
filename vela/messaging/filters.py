"""事件流上的通用过滤器。报表/对账侧用得最多,注意输入是裸 dict,
别把 EventBatch.merge_all 的结果当事件传进来(drop_unavailable 就是
专门滤这种脏数据的)。
"""

from __future__ import annotations

from typing import Any

from vela.domain.shared.events import UNAVAILABLE


def by_type(events: list[dict], pattern: str) -> list[dict]:
    """按类型筛。"order.*" 前缀匹配,其余精确匹配。"""
    if pattern.endswith(".*"):
        prefix = pattern[:-1]  # 保留结尾的 "."
        return [e for e in events if str(e.get("type", "")).startswith(prefix)]
    return [e for e in events if e.get("type") == pattern]


def drop_unavailable(events: list[Any]) -> list[Any]:
    """滤掉 UNAVAILABLE 占位和 merge_all 结果型 dict。

    老管道里偶发把 {"total": ..., "types": ..., "newest": ...} 混进
    事件流,下游炸了很久才查出来(#VT-2078),入口统一滤。
    """
    out: list[Any] = []
    for e in events:
        if isinstance(e, dict):
            if e.get("type") == UNAVAILABLE["type"]:
                continue
            if "total" in e and "types" in e and "newest" in e:
                continue
        out.append(e)
    return out


def only_traced(events: list[dict]) -> list[dict]:
    """只留带 trace 的事件。没 trace 的多半是老调用方裸发的。"""
    return [e for e in events if e.get("trace")]
