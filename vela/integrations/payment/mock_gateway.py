# -*- coding: utf-8 -*-
"""内存模拟支付网关。单测/联调用,别接进生产路径。

可编程失败:fail_next 压栈,每次 pay/refund 弹出一个按它走。
"""

from __future__ import annotations

import itertools

from vela.integrations.payment.errors import PaymentDeclinedError
from vela.integrations.payment.gateway import (
    PaymentRequest,
    PaymentResult,
    STATUS_FAILED,
    STATUS_PAID,
    STATUS_PENDING,
    STATUS_REFUNDED,
)


class MockPaymentGateway:
    """实现 PaymentGateway 协议。"""

    def __init__(self):
        # 可编程失败队列:"declined" / "error",空了就走正常路径
        self.fail_next: list[str] = []
        self._seq = itertools.count(1)
        self._paid: dict[str, PaymentResult] = {}
        self._refunded: dict[str, list[PaymentResult]] = {}
        self.calls: list[tuple[str, str]] = []  # 断言用调用记录

    # -- PaymentGateway ---------------------------------------------------

    def pay(self, req: PaymentRequest) -> PaymentResult:
        self.calls.append(("pay", req.order_no))
        if req.order_no in self._paid:
            # 模拟渠道幂等行为:同单重复发起返回原结果
            return self._paid[req.order_no]
        self._maybe_fail(req.order_no)
        result = PaymentResult(
            status=STATUS_PENDING,
            gateway_trade_no=f"MOCK{next(self._seq):010d}",
            raw={"mock": True, "order_no": req.order_no},
        )
        self._paid[req.order_no] = result
        return result

    def refund(
        self, order_no: str, refund_no: str, amount, reason: str = ""
    ) -> PaymentResult:
        self.calls.append(("refund", order_no))
        origin = self._paid.get(order_no)
        if origin is None or origin.status not in (STATUS_PAID, STATUS_PENDING):
            self._maybe_fail(order_no)
            result = PaymentResult(status=STATUS_FAILED, raw={"reason": "order not paid"})
            self._refunded.setdefault(order_no, []).append(result)
            return result
        self._maybe_fail(order_no)
        result = PaymentResult(
            status=STATUS_REFUNDED,
            gateway_trade_no=origin.gateway_trade_no,
            raw={"refund_no": refund_no, "amount": str(amount), "reason": reason},
        )
        self._refunded.setdefault(order_no, []).append(result)
        return result

    def query(self, order_no: str) -> PaymentResult:
        self.calls.append(("query", order_no))
        found = self._paid.get(order_no)
        if found is None:
            return PaymentResult(status=STATUS_FAILED, raw={"reason": "not found"})
        return found

    # -- 测试辅助 ---------------------------------------------------------

    def settle(self, order_no: str, ok: bool = True) -> PaymentResult:
        """手动推进到终态,模拟渠道异步回调到达。"""
        result = self._paid.get(order_no)
        if result is None:
            raise KeyError(order_no)
        result.status = STATUS_PAID if ok else STATUS_FAILED
        return result

    def _maybe_fail(self, order_no: str) -> None:
        if not self.fail_next:
            return
        mode = self.fail_next.pop(0)
        if mode == "declined":
            raise PaymentDeclinedError(
                f"模拟拒绝: {order_no}", detail={"mode": mode}
            )
        raise RuntimeError(f"模拟渠道故障: {order_no}")
