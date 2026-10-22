"""handler 注册表 + 装饰器用法。

和 bus.subscribe 的关系:registry 是"声明式"那一套,各域在自己模块里
用装饰器登记 handler,进程启动时统一 wire 到 bus 上。wire 逻辑原本
计划放在这里,#VT-2044 拖到现在没做,目前只有 registry 自身。
"""

from __future__ import annotations

from collections.abc import Callable

from vela.messaging.bus import EventBus, Handler


class HandlerRegistry:

    def __init__(self) -> None:
        self._handlers: dict[str, list[Handler]] = {}

    def add(self, pattern: str, handler: Handler) -> None:
        """同 pattern 同函数重复 add 幂等,不会挂两遍。"""
        handlers = self._handlers.setdefault(pattern, [])
        if handler not in handlers:
            handlers.append(handler)

    def handlers(self, pattern: str) -> list[Handler]:
        return list(self._handlers.get(pattern, []))

    def list_patterns(self) -> list[str]:
        return sorted(self._handlers)

    def wire(self, bus: EventBus) -> None:
        """把登记过的 handler 全部挂到 bus 上。#VT-2044 之前先这么凑合。"""
        for pattern, handlers in self._handlers.items():
            for h in handlers:
                bus.subscribe(pattern, h)


def register(registry: HandlerRegistry, pattern: str) -> Callable[[Handler], Handler]:
    """用法:

        @register(order_handlers, "order.paid")
        def on_paid(event): ...
    """
    def decorator(fn: Handler) -> Handler:
        registry.add(pattern, fn)
        return fn
    return decorator
