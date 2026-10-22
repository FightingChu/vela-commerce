"""HTTP 支付网关适配器,走 BaseClient。

对端是公司统一支付网关(不是渠道直连),报文就是字典进字典出,
字段名沿用网关 v2 的 snake_case。渠道直连(微信/支付宝官方 API)
不在本包范围,那种要自己管证书,另开适配器。
"""

from __future__ import annotations

from decimal import Decimal

from vela.config.errors import ExternalServiceError
from vela.config.logging import get_logger
from vela.integrations.base import BaseClient
from vela.integrations.payment.errors import (
    DuplicatePaymentError,
    GatewayTimeoutError,
    PaymentDeclinedError,
)
from vela.integrations.payment.gateway import (
    STATUS_FAILED,
    STATUS_PENDING,
    STATUS_REFUNDED,
    PaymentRequest,
    PaymentResult,
)

log = get_logger(__name__)

# 网关错误码 -> 内部异常。没列进表的走兜底 ExternalServiceError
_ERROR_MAP = {
    "DECLINED": PaymentDeclinedError,
    "RISK_REJECT": PaymentDeclinedError,
    "DUPLICATE": DuplicatePaymentError,
    "TIMEOUT": GatewayTimeoutError,
}

# 网关支付状态 -> 内部状态
_STATUS_MAP = {
    "CREATED": STATUS_PENDING,
    "PROCESSING": STATUS_PENDING,
    "SUCCESS": "paid",
    "FAIL": STATUS_FAILED,
    "REFUNDED": STATUS_REFUNDED,
    "CLOSED": STATUS_FAILED,
}


class HttpPaymentGateway:
    """实现 PaymentGateway 协议。

    breaker 可选传入,支付这种下游挂了宁可快速失败也别把订单线程堆死。
    """

    def __init__(
        self,
        base_url: str,
        merchant_no: str,
        transport=None,
        timeout: float = 5.0,
        breaker=None,
    ):
        # 支付网关 SLA 是 2s,但大促时回调堆积会拖慢响应,5s 是妥协值
        self._client = BaseClient(
            base_url, transport=transport, timeout=timeout, max_retries=1, breaker=breaker
        )
        self._merchant_no = merchant_no

    # -- PaymentGateway ---------------------------------------------------

    def pay(self, req: PaymentRequest) -> PaymentResult:
        payload = {
            "merchant_no": self._merchant_no,
            "out_trade_no": req.order_no,
            "amount": str(req.amount.quantize(Decimal("0.01"))),
            "currency": req.currency,
            "channel": req.channel,
            "subject": req.subject,
            "metadata": req.metadata,
        }
        data = self._client.request("POST", "/v2/payments", json_body=payload)
        return self._to_result(data)

    def refund(self, order_no, refund_no, amount, reason="") -> PaymentResult:
        payload = {
            "merchant_no": self._merchant_no,
            "out_trade_no": order_no,
            "out_refund_no": refund_no,
            "amount": str(amount.quantize(Decimal("0.01"))),
            "reason": reason,
        }
        data = self._client.request("POST", "/v2/refunds", json_body=payload)
        return self._to_result(data)

    def query(self, order_no: str) -> PaymentResult:
        data = self._client.request("GET", f"/v2/payments/{order_no}")
        return self._to_result(data)

    # -- internal ---------------------------------------------------------

    def _to_result(self, data) -> PaymentResult:
        if not isinstance(data, dict):
            raise ExternalServiceError("支付网关返回了非对象报文", detail={"body": str(data)[:256]})

        err_code = data.get("error_code")
        if err_code:
            exc = _ERROR_MAP.get(err_code, ExternalServiceError)
            raise exc(f"支付网关错误 {err_code}: {data.get('error_msg', '')}", detail=data)

        status = _STATUS_MAP.get(data.get("status", ""), STATUS_PENDING)
        return PaymentResult(
            status=status,
            gateway_trade_no=data.get("trade_no", ""),
            raw=data,
        )
