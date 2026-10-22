"""支付回调入口。验签在 integrations/payment/callback.py,这里只搬运。

secret 从 settings.extra 读,不走环境变量直连,轮换逻辑在部署层。
"""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from vela.config.errors import ConfigError, ValidationError
from vela.config.settings import get_settings

bp = Blueprint("payment_callbacks", __name__, url_prefix="/api/v1/payment-callbacks")


@bp.post("")
def receive_callback():
    secret = get_settings().extra.get("payment_callback_secret")
    if not secret:
        raise ConfigError("payment_callback_secret 未配置,拒收回调")
    body = request.get_data() or b""
    if not body:
        raise ValidationError("回调报文为空")

    from vela.integrations.payment.callback import parse_callback

    # parse_callback 验签失败抛 CallbackVerifyError(403 档),原样放行给全局 handler
    headers = dict(request.headers.items())
    event = parse_callback(body, headers, secret)
    return jsonify(
        {
            "accepted": True,
            "order_no": event.order_no,
            "gateway_trade_no": event.gateway_trade_no,
        }
    )
