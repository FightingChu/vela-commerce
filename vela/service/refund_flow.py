"""退款流程编排。申请 -> 审核 -> 打款完成,顺带把券退了。

refund 域只管单据状态,跨域的收尾(退券/回补)在这层串——
mark_refund_done 之后订单到 REFUNDED,核销过的券原样退回
(CouponService.release 幂等,没记录返回空列表)。
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from vela.config.errors import ValidationError
from vela.config.logging import get_logger
from vela.domain.order import (
    RefundModel,
    RefundStatus,
    approve_refund,
    mark_refund_done,
    request_refund,
)
from vela.domain.promotion import CouponService
from vela.service import audit_bridge, notifiers, validation

log = get_logger(__name__)


def apply_refund(
    session: Session,
    order_sn: str,
    amount,
    reason: str,
    *,
    token: str | None = None,
    operator: str | None = None,
) -> RefundModel:
    """申请退款,订单推到 REFUNDING。幂等 token 命中抛 DuplicateOrderError。"""
    validation.require_sn(order_sn)
    amount = validation.require_money(amount, "amount", allow_zero=False)

    refund = request_refund(session, order_sn, amount, reason, token=token)
    # request_refund 把事件挂在 refund.events 上(不入库),这里统一出口
    events = list(getattr(refund, "events", []))
    if events:
        notifiers.fanout(session, events)
    audit_bridge.record_admin_action(
        session,
        action="refund.applied",
        target_type="refund",
        target_id=refund.refund_sn,
        detail={"order_sn": order_sn, "amount": str(amount), "operator": operator},
    )
    return refund


def approve(session: Session, refund_sn: str, *, reviewer: str) -> RefundModel:
    """审核通过。打款还早,APPROVED 只是排队等出纳。"""
    validation.require_non_empty_str(reviewer, "reviewer")
    refund = approve_refund(session, refund_sn)
    audit_bridge.record_admin_action(
        session,
        action="refund.approved",
        target_type="refund",
        target_id=refund_sn,
        detail={"reviewer": reviewer},
    )
    return refund


def complete(session: Session, refund_sn: str, *, operator: str | None = None) -> RefundModel:
    """打款完成:退款 DONE、订单 REFUNDED、券退回,一个事务收尾。"""
    refund = mark_refund_done(session, refund_sn)
    released = CouponService(session).release(refund.order_sn)
    if released:
        log.info(
            "refund_coupons_released",
            refund_sn=refund_sn,
            count=len(released),
        )
    events = list(getattr(refund, "events", []))
    if events:
        notifiers.fanout(session, events)
    audit_bridge.record_admin_action(
        session,
        action="refund.completed",
        target_type="refund",
        target_id=refund_sn,
        detail={"operator": operator, "coupons_released": len(released)},
    )
    return refund


def list_pending(session: Session, *, limit: int = 50) -> list[RefundModel]:
    """审核队列:PENDING 按申请时间正序(先来先审)。"""
    stmt = (
        select(RefundModel)
        .where(RefundModel.status == RefundStatus.PENDING.value)
        .order_by(RefundModel.applied_at)
        .limit(limit)
    )
    return list(session.execute(stmt).scalars())
