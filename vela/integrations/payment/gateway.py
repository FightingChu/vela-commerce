"""支付网关协议与数据结构。

status 取值就这四种,别私自加:
- pending: 已受理未终态(渠道异步回调前都是这个)
- paid / failed: 终态
- refunded: 退款成功(部分退款时 amount 带退款金额,看 metadata)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Protocol

# 支付单状态。渠道状态字段的映射在各 gateway 自己的 _STATUS_MAP 里
STATUS_PENDING = "pending"
STATUS_PAID = "paid"
STATUS_FAILED = "failed"
STATUS_REFUNDED = "refunded"


@dataclass
class PaymentRequest:
    order_no: str
    amount: Decimal
    currency: str = "CNY"
    channel: str = "wechat"          # wechat / alipay / unionpay
    subject: str = ""                # 商品摘要,账单里给用户看的
    metadata: dict[str, str] = field(default_factory=dict)

    def __post_init__(self):
        if not self.order_no:
            raise ValueError("order_no 不能为空")
        if self.amount <= 0:
            # 0 元单走不到支付,别让垃圾请求出门
            raise ValueError(f"金额必须大于 0: {self.amount}")


@dataclass
class PaymentResult:
    status: str
    gateway_trade_no: str = ""       # 渠道流水号,对账靠它
    raw: dict[str, Any] = field(default_factory=dict)  # 渠道原始报文,排障用


class PaymentGateway(Protocol):
    """渠道接入实现这个协议即可,上层(order/refund 服务)只认协议。"""

    def pay(self, req: PaymentRequest) -> PaymentResult:
        """发起支付。返回 pending(等回调)或终态。"""
        ...

    def refund(
        self, order_no: str, refund_no: str, amount: Decimal, reason: str = ""
    ) -> PaymentResult:
        ...

    def query(self, order_no: str) -> PaymentResult:
        """查单。超时后核对状态的唯一手段,见 errors.GatewayTimeoutError 注释。"""
        ...
