"""service 用例编排层。domain 是纯域逻辑,这层负责跨域组装和对外
形状(金额 str、时间 iso、查无返 None)。

分层规矩:
- api/http 只 import 本包,不深入 domain;
- 三个契约模块(checkout/order_query/inventory_ops)的公开签名被
  api 并行任务依赖,改动先在 README 的接口表里登记;
- admin/backoffice 入口一律显式传 session、显式给操作人。

历史注:这层最早叫 vela/biz,2025-11 改名 service,老 import 路径
在 legacy/compat_dict.py 里兼容了半年,现在可以删了。
"""

from vela.service.checkout import create_checkout
from vela.service.order_query import get_order_view, list_customer_orders
from vela.service.inventory_ops import stock_view

from vela.service.order_admin import cancel_with_release, close_stale_orders, split_for_fulfillment
from vela.service.refund_flow import apply_refund, approve as approve_refund_flow, complete as complete_refund_flow, list_pending as list_pending_refunds
from vela.service.inventory_admin import adjust_stock, stock_ledger, stock_row
from vela.service.promotion_ops import apply_coupon_to_order, coupon_view, release_order_coupons
from vela.service.coupon_admin import create_coupon, list_valid, set_enabled
from vela.service.settlement_ops import push_settlement
from vela.service.settlement_admin import find_by_period, list_overdue, settlement_view
from vela.service.customer_ops import (
    change_tier,
    customer_view,
    default_address,
    make_default_address,
    register,
)
from vela.service.validation import (
    require_lines,
    require_money,
    require_non_empty_str,
    require_positive_int,
    require_sn,
)
from vela.service.tenant_guard import explicit_tenant, tenant_or_default
from vela.service.error_mapping import status_of, to_payload, to_response
from vela.service.lock_keys import (
    build_lock_key,
    coupon_lock_key,
    order_lock_key,
    settlement_lock_key,
    stock_lock_key,
)
from vela.service.trace import child_trace, ensure_trace
from vela.service.converters import dt_to_iso, line_to_view, money, order_to_view
from vela.service.notifiers import enqueue_outbox, fanout, publish_to_bus
from vela.service.audit_bridge import bridge, record_admin_action
from vela.service.idempotency_store import IdempotencyStore, check_and_mark, get_global_store

__all__ = [
    # 契约
    "create_checkout",
    "get_order_view",
    "list_customer_orders",
    "stock_view",
    # 订单
    "cancel_with_release",
    "split_for_fulfillment",
    "close_stale_orders",
    "apply_refund",
    "approve_refund_flow",
    "complete_refund_flow",
    "list_pending_refunds",
    # 库存
    "adjust_stock",
    "stock_ledger",
    "stock_row",
    # 促销
    "apply_coupon_to_order",
    "release_order_coupons",
    "coupon_view",
    "create_coupon",
    "set_enabled",
    "list_valid",
    # 结算
    "push_settlement",
    "settlement_view",
    "list_overdue",
    "find_by_period",
    # 客户
    "register",
    "customer_view",
    "change_tier",
    "default_address",
    "make_default_address",
    # 基建
    "require_lines",
    "require_money",
    "require_non_empty_str",
    "require_positive_int",
    "require_sn",
    "explicit_tenant",
    "tenant_or_default",
    "status_of",
    "to_payload",
    "to_response",
    "build_lock_key",
    "order_lock_key",
    "stock_lock_key",
    "settlement_lock_key",
    "coupon_lock_key",
    "ensure_trace",
    "child_trace",
    "money",
    "dt_to_iso",
    "line_to_view",
    "order_to_view",
    "publish_to_bus",
    "enqueue_outbox",
    "fanout",
    "bridge",
    "record_admin_action",
    "IdempotencyStore",
    "get_global_store",
    "check_and_mark",
]
