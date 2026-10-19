"""死信日志。内存版,进程重启即丢——落库方案在 #VT-2135,没排期。

先撑着报警用:运维脚本定期 snapshot 上报,超阈值就告警。
"""

from __future__ import annotations

from typing import Any


class DeadLetterLog:
    """有界 list 封装,超 cap 丢最旧的。"""

    def __init__(self, cap: int = 1000):
        self.cap = cap
        self._entries: list[dict[str, Any]] = []

    def append(self, event: dict, reason: str) -> None:
        self._entries.append({"event": dict(event), "reason": reason})
        if len(self._entries) > self.cap:
            del self._entries[: len(self._entries) - self.cap]

    def snapshot(self) -> list[dict[str, Any]]:
        """浅拷贝,调用方随便改不污染内部状态。"""
        return [dict(e) for e in self._entries]

    def clear(self) -> None:
        self._entries.clear()

    def __len__(self) -> int:
        return len(self._entries)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<DeadLetterLog {len(self._entries)}/{self.cap}>"
