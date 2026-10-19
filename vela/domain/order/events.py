"""订单域事件类型。

type 约定 order.<动作>。trace 以前塞在 order.remark 里拼字符串,太丑,
2025-10 起事件自带 trace 字段(shared/events.make_event),老消费方
不读它,兼容。
"""

from __future__ import annotations

from vela.domain.shared import make_event

EVENT_ORDER_CREATED = "order.created"
EVENT_ORDER_PAID = "order.paid"
EVENT_ORDER_CANCELLED = "order.cancelled"
EVENT_ORDER_SPLIT = "order.split"
EVENT_REFUND_REQUESTED = "order.refund_requested"
EVENT_REFUNDED = "order.refunded"


def build_order_event(etype: str, order, extra: dict | None = None, *, trace: str | None = None) -> dict:
    """order 参数是 Order 聚合(鸭子类型,只要有 order_sn/customer_id/...)。"""
    payload = {
        "order_sn": order.order_sn,
        "customer_id": order.customer_id,
        "status": order.status,
        "total_amount": str(order.total_amount),
    }
    if extra:
        payload.update(extra)
    return make_event(etype, payload, trace=trace)
