"""订单状态机。

PAID -> CANCELLED 没有边:已支付单走退款,不走取消。2024-03 订单
改造定的约定,老网关上还有人靠先取消再退款的脏路径,别加回来。
"""

from __future__ import annotations

import enum

from vela.domain.order.order_errors import OrderStateError
from vela.domain.shared import StateMachine


class OrderStatus(str, enum.Enum):
    CREATED = "created"
    PAID = "paid"
    PARTIAL_SHIPPED = "partial_shipped"
    SHIPPED = "shipped"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    #: 系统关单(超时未支付)。和 CANCELLED 的区别:关单是系统行为,
    #: 报表侧要分开统计
    CLOSED = "closed"
    REFUNDING = "refunding"
    REFUNDED = "refunded"


class OrderLineStatus(str, enum.Enum):
    ACTIVE = "active"
    SHIPPED = "shipped"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"


#: 终态,只进不出
TERMINAL_STATUSES = ("CANCELLED", "CLOSED", "COMPLETED", "REFUNDED")


def _state_name(value) -> str:
    """枚举或裸字符串都收,统一成 name 形式(大写)。"""
    if isinstance(value, OrderStatus):
        return value.name
    return str(value).upper()


class OrderStateMachine(StateMachine):
    """transitions 里值是"合法动作名",审计日志靠它区分谁干的。"""

    transitions: dict[str, dict[str, str]] = {
        "CREATED": {
            "PAID": "pay",
            "CANCELLED": "cancel",
            "CLOSED": "close",
        },
        "PAID": {
            "PARTIAL_SHIPPED": "ship",
            "SHIPPED": "ship",
            "REFUNDING": "request_refund",
        },
        "PARTIAL_SHIPPED": {
            "SHIPPED": "ship",
            "REFUNDING": "request_refund",
        },
        "SHIPPED": {
            "COMPLETED": "complete",
            "REFUNDING": "request_refund",
        },
        "REFUNDING": {
            "REFUNDED": "refund_done",
            # 退款被驳回回到 PAID,动作不是 pay,mark_paid 里会拦
            "PAID": "refund_rejected",
        },
        "CANCELLED": {},
        "CLOSED": {},
        "COMPLETED": {},
        "REFUNDED": {},
    }

    @classmethod
    def can_transition(cls, current, target) -> bool:
        return super().can_transition(_state_name(current), _state_name(target))

    @classmethod
    def assert_transition(cls, current, target) -> None:
        # 基类抛的是裸 ConflictError,order 域统一换成 OrderStateError,
        # 不然调用方没法按域 catch
        cur, tgt = _state_name(current), _state_name(target)
        if not super().can_transition(cur, tgt):
            allowed = sorted(cls.transitions.get(cur, {}))
            raise OrderStateError(
                f"订单状态 {cur} 不允许流转到 {tgt}",
                detail={"current": cur, "target": tgt, "allowed": allowed},
            )

    @classmethod
    def action_for(cls, current, target) -> str | None:
        return super().action_for(_state_name(current), _state_name(target))
