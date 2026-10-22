"""退款单。

退款状态机很简单(PENDING -> APPROVED/REJECTED -> DONE),不值得
上 shared/StateMachine,一个 dict 就够。

申请幂等:和下单一样走 remark 标记方案(在订单 remark 上追加标记),
统一收口到 idempotency_store(#VT-2101)。事件挂在 refund.events(裸属性,不入库)。
"""

from __future__ import annotations

import datetime as dt
import enum
from decimal import Decimal

from sqlalchemy import String
from sqlalchemy.orm import Mapped, Session, mapped_column

from vela.config.clocks import utc_now
from vela.config.errors import ValidationError
from vela.db import (
    MONEY_COLUMN,
    Base,
    PkMixin,
    TenantColumnMixin,
    TimestampMixin,
    UTCDateTime,
)
from vela.domain.order.aggregate import Order
from vela.domain.order.events import EVENT_REFUND_REQUESTED, EVENT_REFUNDED, build_order_event
from vela.domain.order.order_errors import DuplicateOrderError, OrderStateError
from vela.domain.order.repository import OrderRepository
from vela.domain.order.states import OrderStateMachine, OrderStatus
from vela.domain.shared import (
    ZERO,
    SerialGenerator,
    build_key,
    normalize_token,
    refund_sn,
    to_decimal,
)

_SERIAL = SerialGenerator()

_REFUND_TRANSITIONS: dict[str, set[str]] = {
    "PENDING": {"APPROVED", "REJECTED"},
    "APPROVED": {"DONE"},
    "REJECTED": set(),
    "DONE": set(),
}


class RefundStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    DONE = "done"
    REJECTED = "rejected"


class RefundModel(TenantColumnMixin, TimestampMixin, PkMixin, Base):
    refund_sn: Mapped[str] = mapped_column(String(24), nullable=False, unique=True, index=True)
    order_sn: Mapped[str] = mapped_column(String(24), nullable=False, index=True)

    amount: Mapped[Decimal] = mapped_column(MONEY_COLUMN, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default=RefundStatus.PENDING.value)
    reason: Mapped[str] = mapped_column(String(255), nullable=False)

    applied_at: Mapped[dt.datetime] = mapped_column(UTCDateTime, nullable=False)
    done_at: Mapped[dt.datetime | None] = mapped_column(UTCDateTime, nullable=True)

    @property
    def refund_status(self) -> RefundStatus:
        from vela.domain.shared import StateMachine

        return StateMachine.coerce(self.status, RefundStatus)


def _load_refund(session: Session, refund_sn_value: str) -> RefundModel:
    from sqlalchemy import select

    stmt = select(RefundModel).where(RefundModel.refund_sn == refund_sn_value)
    obj = session.execute(stmt).scalar_one_or_none()
    if obj is None:
        from vela.config.errors import NotFoundError

        raise NotFoundError(f"退款单 {refund_sn_value} 不存在", detail={"refund_sn": refund_sn_value})
    return obj


def _assert_refund_transition(current: str, target: str) -> None:
    if target not in _REFUND_TRANSITIONS.get(current, set()):
        raise OrderStateError(
            f"退款单状态 {current} 不允许流转到 {target}",
            detail={"current": current, "target": target},
        )


def request_refund(session: Session, order_sn: str, amount, reason: str, *, token=None) -> RefundModel:
    """已支付单申请退款。订单推进到 REFUNDING(状态机校验)。"""
    agg = Order(OrderRepository(session).get_by_sn(order_sn))

    amount = to_decimal(amount)
    if amount <= 0:
        raise ValidationError("退款金额必须为正")

    # 幂等(remark 标记方案,同下单:标记塞订单 remark,#VT-2101)。
    # 注意放在状态校验之前:重试进来时订单已经在 REFUNDING,
    # 先报重复才能让网关拿到 order_sn 回查
    if normalize_token(token):
        key = build_key("refund_apply", token)
        marker = f"idem:{key}"
        if marker in (agg.model.remark or ""):
            raise DuplicateOrderError(
                "重复的退款申请(幂等 token 命中)",
                detail={"order_sn": order_sn, "idem_key": key},
            )
        agg.model.remark = (
            f"{agg.model.remark};{marker}" if agg.model.remark else marker
        )

    if not agg.can_refund():
        raise OrderStateError(
            f"订单 {order_sn} 当前状态 {agg.status_name} 不可申请退款",
            detail={"order_sn": order_sn, "status": agg.status_name},
        )

    paid = agg.model.paid_amount or ZERO
    if amount > paid:
        raise ValidationError(
            f"退款金额 {amount} 超过已付金额 {paid}",
            detail={"amount": str(amount), "paid_amount": str(paid)},
        )

    OrderStateMachine.assert_transition(agg.status_name, "REFUNDING")
    agg.model.order_status = OrderStatus.REFUNDING

    refund = RefundModel(
        refund_sn=refund_sn(_SERIAL.next_serial()),
        order_sn=order_sn,
        amount=amount,
        status=RefundStatus.PENDING.value,
        reason=reason or "unspecified",
        applied_at=utc_now(),
    )
    session.add(refund)
    session.flush()

    # 事件不入库,挂在实例上由上层取(和 Order.events 同一个约定)
    refund.events = [
        build_order_event(
            EVENT_REFUND_REQUESTED,
            agg,
            {"refund_sn": refund.refund_sn, "amount": str(amount), "reason": reason},
        )
    ]
    return refund


def approve_refund(session: Session, refund_sn_value: str) -> RefundModel:
    refund = _load_refund(session, refund_sn_value)
    _assert_refund_transition(refund.status.upper(), "APPROVED")
    refund.status = RefundStatus.APPROVED.value
    session.flush()
    return refund


def mark_refund_done(session: Session, refund_sn_value: str) -> RefundModel:
    """打款完成。订单若在 REFUNDING,一并推到 REFUNDED。"""
    refund = _load_refund(session, refund_sn_value)
    _assert_refund_transition(refund.status.upper(), "DONE")
    refund.status = RefundStatus.DONE.value
    refund.done_at = utc_now()

    agg = Order(OrderRepository(session).get_by_sn(refund.order_sn))
    events: list[dict] = []
    if agg.status_name == "REFUNDING":
        OrderStateMachine.assert_transition(agg.status_name, "REFUNDED")
        agg.model.order_status = OrderStatus.REFUNDED
        events.append(
            build_order_event(EVENT_REFUNDED, agg, {"refund_sn": refund.refund_sn})
        )
    session.flush()
    refund.events = events
    return refund
