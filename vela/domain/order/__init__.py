"""order 域。核心域,改动先看 README.md 里的状态机图。

对外高频 API 从包根 re-export,别从子模块深层 import(历史上
aggregate 内部结构调整过一次,外部 from ...aggregate import Order
的全崩了)。

注意本域不 import inventory/pricing/promotion/customer,跨域能力
(reserver/pricer/release_fn)一律构造注入,见 OrderService。
"""

from vela.domain.order.aggregate import Order
from vela.domain.order.cancel import cancel_order
from vela.domain.order.events import (
    EVENT_ORDER_CANCELLED,
    EVENT_ORDER_CREATED,
    EVENT_ORDER_PAID,
    EVENT_ORDER_SPLIT,
    EVENT_REFUND_REQUESTED,
    EVENT_REFUNDED,
    build_order_event,
)
from vela.domain.order.models import OrderLineModel, OrderModel
from vela.domain.order.order_errors import (
    DuplicateOrderError,
    OrderNotFoundError,
    OrderStateError,
)
from vela.domain.order.order_service import OrderService
from vela.domain.order.pricing_hook import DefaultPricer
from vela.domain.order.repository import OrderRepository
from vela.domain.order.returns import (
    RefundModel,
    RefundStatus,
    approve_refund,
    mark_refund_done,
    request_refund,
)
from vela.domain.order.split import split_order
from vela.domain.order.states import (
    TERMINAL_STATUSES,
    OrderLineStatus,
    OrderStateMachine,
    OrderStatus,
)

__all__ = [
    "Order",
    "OrderModel",
    "OrderLineModel",
    "OrderStatus",
    "OrderLineStatus",
    "OrderStateMachine",
    "TERMINAL_STATUSES",
    "OrderService",
    "OrderRepository",
    "OrderStateError",
    "OrderNotFoundError",
    "DuplicateOrderError",
    "DefaultPricer",
    "cancel_order",
    "split_order",
    "request_refund",
    "approve_refund",
    "mark_refund_done",
    "RefundModel",
    "RefundStatus",
    "EVENT_ORDER_CREATED",
    "EVENT_ORDER_PAID",
    "EVENT_ORDER_CANCELLED",
    "EVENT_ORDER_SPLIT",
    "EVENT_REFUND_REQUESTED",
    "EVENT_REFUNDED",
    "build_order_event",
]
