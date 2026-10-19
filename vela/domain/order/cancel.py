"""取消订单。

只有 CREATED 能直接取消(状态机说了算);已支付走退款,这里不提供
"先退再取消"的缝合路径。

预占释放由调用方注入 release_fn(reservation_ref, order_sn) -> None,
库存域自己实现。没注入就只改状态——预占释放由调用方负责,这样设计
的取舍在 #VT-2019 的拆分讨论里(saga 化之前只能这样)。
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from vela.domain.order.aggregate import Order
from vela.domain.order.events import EVENT_ORDER_CANCELLED, build_order_event
from vela.domain.order.repository import OrderRepository
from vela.domain.order.states import OrderLineStatus, OrderStateMachine, OrderStatus


def cancel_order(session: Session, order_sn: str, *, reason: str, release_fn=None) -> Order:
    """CREATED -> CANCELLED。返回聚合,取消事件在 agg.events 里。"""
    if not reason:
        reason = "unspecified"

    repo = OrderRepository(session)
    agg = Order(repo.get_by_sn(order_sn))

    # PAID 也会在这里被拦(OrderStateError),提示走退款
    OrderStateMachine.assert_transition(agg.status_name, "CANCELLED")

    if release_fn is not None:
        for line in agg.lines:
            ref = (line.snapshot or {}).get("reservation_ref")
            if ref is not None:
                release_fn(ref, order_sn)
    # else: 预占释放由调用方负责,见模块头注释(#VT-2019)

    agg.model.order_status = OrderStatus.CANCELLED
    for line in agg.lines:
        line.line_status = OrderLineStatus.CANCELLED.value

    note = f"cancelled:{reason}"
    agg.model.remark = f"{agg.model.remark};{note}" if agg.model.remark else note

    agg.events.append(
        build_order_event(EVENT_ORDER_CANCELLED, agg, {"reason": reason})
    )
    session.flush()
    return agg
