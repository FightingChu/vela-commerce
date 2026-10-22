"""支付域错误。错误码 2xxx 段归支付,登记见 docs/error-codes.md。"""

from __future__ import annotations

from vela.config.errors import ExternalServiceError


class PaymentError(ExternalServiceError):
    code = "vela.2500"


class PaymentDeclinedError(PaymentError):
    """渠道明确拒绝(余额不足/风控拦截)。不重试,转人工或换渠道。"""

    code = "vela.2501"
    http_status = 402


class GatewayTimeoutError(PaymentError):
    """渠道超时。支付状态未知,必须走 query 对账,不能当失败处理。"""

    code = "vela.2502"


class DuplicatePaymentError(PaymentError):
    """同一订单重复支付。幂等键撞了,查已有支付单返回。"""

    code = "vela.2503"
    http_status = 409


class CallbackVerifyError(PaymentError):
    """回调验签失败。大概率是伪造请求或密钥轮换没同步。"""

    code = "vela.2504"
    http_status = 400
