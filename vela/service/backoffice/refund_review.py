"""退款审核工作台。队列 + 通过/驳回,给客服后台用。

驳回入口是这里本地翻状态(returns.py 只给了 approve/done,REJECTED
的边在 _REFUND_TRANSITIONS 里有但没包函数)——按那张表翻,别发明
新边;哪天 returns.py 补了 reject 入口就换过去。
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from vela.config.errors import ValidationError
from vela.config.logging import get_logger
from vela.domain.order import RefundModel, RefundStatus, approve_refund
from vela.service import audit_bridge
from vela.service.converters import dt_to_iso, money

log = get_logger(__name__)

# 与 returns.py 的 _REFUND_TRANSITIONS 对齐,这边只关心 PENDING 的去向
_PENDING_TARGETS = {"APPROVED", "REJECTED"}


def list_pending(session: Session, *, limit: int = 50) -> list[dict]:
    """待审核队列,先申请的排前面。视图带订单上下文要的最低限度字段。"""
    stmt = (
        select(RefundModel)
        .where(RefundModel.status == RefundStatus.PENDING.value)
        .order_by(RefundModel.applied_at)
        .limit(limit)
    )
    rows = session.execute(stmt).scalars().all()
    return [
        {
            "refund_sn": r.refund_sn,
            "order_sn": r.order_sn,
            "amount": money(r.amount),
            "reason": r.reason,
            "applied_at": dt_to_iso(r.applied_at),
        }
        for r in rows
    ]


def approve(session: Session, refund_sn: str, *, reviewer: str) -> RefundModel:
    """审核通过。reviewer 必填——客服后台偶尔丢登录态,宁可不记
    也不能记成 system。"""
    if not reviewer or not str(reviewer).strip():
        raise ValidationError("审核必须带 reviewer")
    refund = approve_refund(session, refund_sn)
    audit_bridge.record_admin_action(
        session,
        action="refund.review_approved",
        target_type="refund",
        target_id=refund_sn,
        detail={"reviewer": reviewer},
    )
    return refund


def reject(
    session: Session,
    refund_sn: str,
    *,
    reviewer: str,
    reason: str = "",
) -> RefundModel:
    """驳回。PENDING -> REJECTED,订单停在 REFUNDING 由人工恢复
    (恢复入口还没做,#VT-2174,先在后台手工改)。"""
    if not reviewer or not str(reviewer).strip():
        raise ValidationError("审核必须带 reviewer")

    stmt = select(RefundModel).where(RefundModel.refund_sn == refund_sn)
    refund = session.execute(stmt).scalar_one_or_none()
    if refund is None:
        from vela.config.errors import NotFoundError

        raise NotFoundError(f"退款单 {refund_sn} 不存在")

    if refund.status.upper() not in _PENDING_TARGETS:
        # 只拦 PENDING;APPROVED 要撤得走线下流程
        raise ValidationError(
            f"退款单 {refund_sn} 状态 {refund.status} 不可驳回",
            detail={"status": refund.status},
        )

    refund.status = RefundStatus.REJECTED.value
    if reason:
        refund.reason = f"{refund.reason};rejected:{reason}"[:255]
    session.flush()

    audit_bridge.record_admin_action(
        session,
        action="refund.review_rejected",
        target_type="refund",
        target_id=refund_sn,
        detail={"reviewer": reviewer, "reason": reason},
    )
    log.info("refund_rejected", refund_sn=refund_sn, reviewer=reviewer)
    return refund
