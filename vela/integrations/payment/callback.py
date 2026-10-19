# -*- coding: utf-8 -*-
"""支付回调:验签 + 幂等键解析。

回调入口是公网可达的,这里的每一行都当不可信输入处理:
- 先验签,验不过直接 400,连 body 都不要解析;
- 幂等键用 domain.shared.build_key,scope 固定 "pay_cb",
  上游拿这个键去重(数据库唯一约束 / redis setnx 都行)。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from vela.domain.shared.idempotency import build_key
from vela.integrations import signing
from vela.integrations.payment.errors import CallbackVerifyError

# 幂等 scope,order 服务侧的同名常量必须保持一致
CB_SCOPE = "pay_cb"


@dataclass
class CallbackEvent:
    order_no: str
    gateway_trade_no: str
    status: str                    # 渠道原始状态,未映射,调用方自己判断
    amount: str                    # 渠道回传金额,字符串原样,比对在订单侧做
    idempotency_key: str
    raw: dict = field(default_factory=dict)


def parse_callback(
    body: bytes | str,
    headers: dict[str, str],
    secret: str,
    *,
    tolerance: float = signing.DEFAULT_TOLERANCE,
) -> CallbackEvent:
    """解析并验证支付回调。

    验签失败抛 CallbackVerifyError;报文缺字段抛 ValueError。
    """
    import json

    timestamp = headers.get(signing.TIMESTAMP_HEADER, "")
    signature = headers.get(signing.SIGNATURE_HEADER, "")
    if not signing.verify(secret, body, signature, timestamp, tolerance):
        raise CallbackVerifyError("支付回调验签失败")

    try:
        payload = json.loads(body if isinstance(body, (bytes, bytearray))
                             else body.encode("utf-8"))
    except (ValueError, UnicodeDecodeError) as e:
        raise ValueError(f"回调报文不是合法 JSON: {e}") from e

    order_no = payload.get("out_trade_no") or ""
    trade_no = payload.get("trade_no") or ""
    if not order_no or not trade_no:
        raise ValueError(f"回调缺少关键字段: out_trade_no/trade_no, got {sorted(payload)}")

    return CallbackEvent(
        order_no=order_no,
        gateway_trade_no=trade_no,
        status=payload.get("status", ""),
        amount=str(payload.get("amount", "")),
        # 幂等键以渠道流水号为 token:渠道对同一笔回调可能重发多次
        idempotency_key=build_key(CB_SCOPE, trade_no),
        raw=payload,
    )
