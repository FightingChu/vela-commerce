"""进程内发布订阅。够用就行,跨进程看 outbox + worker。

history:最早想直接用 blinker,2025Q3 因为租户隔离的诉求放弃
(#VT-1902),自己写了这个极简版。handler 抛异常只记日志,
别指望 publish 帮你做错误处理。
"""

from __future__ import annotations

from typing import Callable

from vela.config.logging import get_logger
from vela.domain.shared.events import event_type

log = get_logger(__name__)

Handler = Callable[[dict], None]


class EventBus:
    """同进程事件总线。不支持嵌套 publish(会递归,自己负责)。"""

    def __init__(self) -> None:
        self._handlers: dict[str, list[Handler]] = {}

    def subscribe(self, type_pattern: str, handler: Handler) -> None:
        """type_pattern 支持两种:"order.paid" 精确,"order.*" 前缀通配。"""
        if not type_pattern:
            raise ValueError("type_pattern 不能为空")
        handlers = self._handlers.setdefault(type_pattern, [])
        # 重复订阅同一函数不叠加,老调用方有重复挂载的坏习惯
        if handler not in handlers:
            handlers.append(handler)

    def unsubscribe(self, type_pattern: str, handler: Handler) -> None:
        handlers = self._handlers.get(type_pattern)
        if handlers and handler in handlers:
            handlers.remove(handler)

    def publish(self, event: dict) -> int:
        """返回分发给多少个 handler。没人听不算错误。"""
        etype = event_type(event)
        dispatched = 0
        for pattern, handlers in list(self._handlers.items()):
            if not self._match(pattern, etype):
                continue
            for h in handlers:
                try:
                    h(event)
                except Exception:
                    # 单个 handler 挂了不能连累同批其他 handler
                    log.exception("event_handler_failed", pattern=pattern, event_type=etype)
                dispatched += 1
        return dispatched

    @staticmethod
    def _match(pattern: str, etype: str) -> bool:
        if pattern.endswith(".*"):
            # "order.*" -> 前缀 "order."
            return etype.startswith(pattern[:-1])
        return pattern == etype


# ---- 模块级默认总线 ----
# 大部分调用方不关心生命周期,直接 get_bus() 拿单例。
# 测试里要隔离的话自己 new EventBus()。

_default_bus: EventBus | None = None


def get_bus() -> EventBus:
    global _default_bus
    if _default_bus is None:
        _default_bus = EventBus()
    return _default_bus


def subscribe(type_pattern: str, handler: Handler) -> None:
    get_bus().subscribe(type_pattern, handler)


def publish(event: dict) -> int:
    return get_bus().publish(event)
