"""库存域事件类型。

消费方:报表侧 EventBatch 聚合 + 风控的实时流。改名等于事故,
只能加新的。#VT-2217 之后统一收敛到这份清单。
"""

from __future__ import annotations

EVENT_STOCK_RESERVED = "inventory.stock_reserved"
EVENT_STOCK_DEDUCTED = "inventory.stock_deducted"
EVENT_STOCK_ROLLED_BACK = "inventory.stock_rolled_back"
EVENT_RESERVATION_CONSUMED = "inventory.reservation_consumed"
EVENT_RESERVATION_RELEASED = "inventory.reservation_released"
EVENT_RESERVATION_TIMED_OUT = "inventory.reservation_timed_out"
EVENT_RECONCILE_DONE = "inventory.reconcile_done"
EVENT_STOCKTAKE_VARIANCE = "inventory.stocktake_variance"

__all__ = [
    "EVENT_RECONCILE_DONE",
    "EVENT_RESERVATION_CONSUMED",
    "EVENT_RESERVATION_RELEASED",
    "EVENT_RESERVATION_TIMED_OUT",
    "EVENT_STOCKTAKE_VARIANCE",
    "EVENT_STOCK_DEDUCTED",
    "EVENT_STOCK_RESERVED",
    "EVENT_STOCK_ROLLED_BACK",
]
