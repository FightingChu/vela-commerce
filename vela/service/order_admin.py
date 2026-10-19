"""订单管理端操作。session 由调用方显式传入(http 层请求会话/job 会话),
这里不做会话生命周期管理——admin 操作经常批量,会话语义差异大。

取消时预占释放:cancel_order 的 release_fn 契约是
(ref, order_sn) -> None,直接接 ReservationRepository.release。
#VT-2019 里 saga 化讨论完之前的妥协方案,先这样。
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy.orm import Session

from vela.config.errors import ValidationError
from vela.config.logging import get_logger
from vela.domain.order import (
    Order,
    OrderRepository,
    cancel_order,
    split_order,
)
from vela.domain.inventory.reservation_repo import ReservationRepository
from vela.service import audit_bridge, validation

log = get_logger(__name__)


def _release_reservation(session: Session):
    def release_fn(ref, order_sn: str) -> None:
        ReservationRepository(session).release(ref)

    return release_fn


def cancel_with_release(
    session: Session,
    order_sn: str,
    *,
    reason: str,
    operator: str | None = None,
) -> Order:
    """CREATED -> CANCELLED,预占一并释放。PAID 单会被状态机拦,提示走退款。"""
    validation.require_sn(order_sn)
    if not reason:
        raise ValidationError("取消必须给原因(审计要看)")

    agg = cancel_order(
        session, order_sn, reason=reason, release_fn=_release_reservation(session)
    )
    audit_bridge.record_admin_action(
        session,
        action="order.cancelled",
        target_type="order",
        target_id=order_sn,
        detail={"reason": reason, "operator": operator},
    )
    log.info("order_cancelled", order_sn=order_sn, operator=operator)
    return agg


def split_for_fulfillment(
    session: Session,
    order_sn: str,
    line_indexes: list[int],
    *,
    operator: str | None = None,
) -> tuple[Order, Order]:
    """多仓发货拆单。金额守恒由 split_order 保证,这里只加审计。"""
    validation.require_sn(order_sn)
    if not line_indexes:
        raise ValidationError("line_indexes 不能为空")

    parent, child = split_order(session, order_sn, line_indexes)
    audit_bridge.record_admin_action(
        session,
        action="order.split",
        target_type="order",
        target_id=order_sn,
        detail={
            "child_order_sn": child.model.order_sn,
            "moved_line_count": len(line_indexes),
            "operator": operator,
        },
    )
    return parent, child


def close_stale_orders(
    session: Session,
    before: dt.datetime,
    *,
    limit: int = 100,
    operator: str | None = None,
) -> list[str]:
    """超时未支付关单 job 的入口。返回关掉的单号列表。

    释放预占跟着走;事件在 agg.events 里,调用方收走发 outbox。
    """
    repo = OrderRepository(session)
    closed: list[str] = []
    for model in repo.list_waiting_payment(before, limit=limit):
        agg = cancel_order(
            session,
            model.order_sn,
            reason="timeout",
            release_fn=_release_reservation(session),
        )
        closed.append(agg.model.order_sn)
    if closed:
        audit_bridge.record_admin_action(
            session,
            action="order.batch_closed",
            target_type="order",
            target_id=",".join(closed[:10]),
            detail={"count": len(closed), "before": before.isoformat(), "operator": operator},
        )
        session.flush()
    return closed
