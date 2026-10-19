# -*- coding: utf-8 -*-
"""支付适配器。入口看 README.md。"""

from vela.integrations.payment.callback import CB_SCOPE, CallbackEvent, parse_callback
from vela.integrations.payment.errors import (
    CallbackVerifyError,
    DuplicatePaymentError,
    GatewayTimeoutError,
    PaymentDeclinedError,
    PaymentError,
)
from vela.integrations.payment.gateway import (
    PaymentGateway,
    PaymentRequest,
    PaymentResult,
)
from vela.integrations.payment.http_gateway import HttpPaymentGateway
from vela.integrations.payment.mock_gateway import MockPaymentGateway

__all__ = [
    "CB_SCOPE",
    "CallbackEvent",
    "parse_callback",
    "PaymentError",
    "PaymentDeclinedError",
    "GatewayTimeoutError",
    "DuplicatePaymentError",
    "CallbackVerifyError",
    "PaymentGateway",
    "PaymentRequest",
    "PaymentResult",
    "HttpPaymentGateway",
    "MockPaymentGateway",
]
