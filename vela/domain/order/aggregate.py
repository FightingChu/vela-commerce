"""订单聚合。领域操作都挂在 Order 上,service 层只做编排。

Order 只包 model + lines,不持有 session;写库由调用方 flush/commit。
事件收集在 Order.events(裸 dict,发给谁由上层决定,域内不发 MQ)。
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

from vela.config.clocks import utc_now
from vela.config.errors import ValidationError
from vela.domain.order.models import OrderLineModel, OrderModel
from vela.domain.order.states import OrderStateMachine, OrderStatus
from vela.domain.shared import (
    ZERO,
    allocate_pro_rata,
    round_half_up,
    sum_amounts,
    to_decimal,
)


class Order:
    """包装 OrderModel + lines。别直接拿 model 出去改,改了合计就对不上。"""

    def __init__(self, model: OrderModel, lines: list[OrderLineModel] | None = None):
        self.model = model
        # 不传 lines 就用 relationship(要求 model 在 session 里或已 load)
        self.lines: list[OrderLineModel] = list(lines) if lines is not None else list(model.lines)
        self.events: list[dict] = []

    # ---- 金额 ----

    def recompute_total(self) -> Decimal:
        """total = 行金额合计 - 行优惠合计。优惠分摊后必须调一次。"""
        if not self.lines:
            raise ValidationError("订单没有行,无法计算合计")
        gross = sum_amounts(*(line.line_amount for line in self.lines))
        discount = sum_amounts(
            *(line.discount_share if line.discount_share is not None else ZERO for line in self.lines)
        )
        if discount > gross:
            # 正常走不到这里,分摊入口有校验;防的是有人手动改行优惠
            raise ValidationError(
                "优惠合计超过行金额合计", detail={"gross": str(gross), "discount": str(discount)}
            )
        self.model.discount_amount = discount
        self.model.total_amount = round_half_up(gross - discount)
        return self.model.total_amount

    def allocate_discount(self, total_discount, weights=None) -> list[Decimal]:
        """把订单级优惠摊到行,缺省按行金额权重。

        allocate_pro_rata 保证份额合计严格等于 total_discount
        (余数给最后一份),对账才过得去。
        """
        total_discount = to_decimal(total_discount)
        if total_discount < 0:
            raise ValidationError("优惠金额不能为负")
        if not self.lines:
            raise ValidationError("订单没有行,无法分摊优惠")
        if weights is None:
            weights = [line.line_amount for line in self.lines]
        if len(list(weights)) != len(self.lines):
            raise ValidationError("权重数量和行数不一致")
        parts = allocate_pro_rata(total_discount, weights)
        for line, part in zip(self.lines, parts, strict=True):
            line.discount_share = part
        self.model.discount_amount = sum_amounts(*parts)
        self.recompute_total()
        return parts

    # ---- 状态 ----

    @property
    def status_name(self) -> str:
        return self.model.order_status.name

    def can_cancel(self) -> bool:
        # CREATED 之外都不允许直接取消(PAID 走退款,状态机里没这条边)
        return OrderStateMachine.can_transition(self.status_name, "CANCELLED")

    def can_refund(self) -> bool:
        return OrderStateMachine.can_transition(self.status_name, "REFUNDING")

    def mark_paid(self, paid_at: dt.datetime | None = None) -> None:
        """支付回调驱动。只接受 pay 动作,退款驳回回到 PAID 的边不算支付。"""
        current = self.status_name
        OrderStateMachine.assert_transition(current, "PAID")
        if OrderStateMachine.action_for(current, "PAID") != "pay":
            raise ValidationError(
                f"动作不合法:{current} -> PAID 不是 pay",
                detail={"action": OrderStateMachine.action_for(current, "PAID")},
            )
        self.model.order_status = OrderStatus.PAID
        self.model.paid_at = paid_at or utc_now()
        # 全额支付假设;组合支付(余额+现金)进来时这里要改,见 #VT-2073
        self.model.paid_amount = self.model.total_amount

    # ---- 便捷透传 ----

    def __getattr__(self, name: str):
        # 未显式声明的属性透传给 model(order_sn/customer_id/total_amount...)
        if name.startswith("_") or name == "model":
            raise AttributeError(name)
        return getattr(self.model, name)

    def __repr__(self) -> str:  # pragma: no cover - debug 用
        return f"<Order {self.model.order_sn} {self.status_name}>"
