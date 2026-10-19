# -*- coding: utf-8 -*-
"""HMAC-SHA256 签名/验签。

报文格式跟支付网关对齐:f"{timestamp}.{body}",签名 hex。
timestamp 容差默认 5 分钟——跨秒级时钟漂移靠这个兜,别为了"更安全"
调到 60s 以下,生产机器 NTP 抖一下回调就全被拒,#VT-2903 教训。
"""

from __future__ import annotations

import hashlib
import hmac
import time

# 回调/外发 webhook 统一用这两个头
TIMESTAMP_HEADER = "X-Vela-Timestamp"
SIGNATURE_HEADER = "X-Vela-Signature"

DEFAULT_TOLERANCE = 300.0


def _canonical(timestamp: int | str, body: bytes | str) -> bytes:
    if isinstance(body, str):
        body = body.encode("utf-8")
    return str(timestamp).encode("ascii") + b"." + body


def sign(secret: str, body: bytes | str, timestamp: int | str | None = None) -> str:
    """生成签名。timestamp 不传取当前时间(秒级)。"""
    if not secret:
        raise ValueError("签名 secret 不能为空")
    ts = timestamp if timestamp is not None else int(time.time())
    return hmac.new(
        secret.encode("utf-8"), _canonical(ts, body), hashlib.sha256
    ).hexdigest()


def sign_headers(
    secret: str, body: bytes | str, timestamp: int | None = None
) -> dict[str, str]:
    """外发请求直接把这两个头带上即可。"""
    ts = timestamp if timestamp is not None else int(time.time())
    return {
        TIMESTAMP_HEADER: str(ts),
        SIGNATURE_HEADER: sign(secret, body, ts),
    }


def verify(
    secret: str,
    body: bytes | str,
    signature: str,
    timestamp: int | str,
    tolerance: float = DEFAULT_TOLERANCE,
    *,
    now: float | None = None,
) -> bool:
    """验签。签名不匹配或时间戳超容差都返回 False(不抛,回调入口要稳)。

    now 参数给测试注入时钟用,生产别传。
    """
    try:
        ts = int(timestamp)
    except (TypeError, ValueError):
        return False
    current = now if now is not None else time.time()
    if abs(current - ts) > tolerance:
        return False
    expected = sign(secret, body, ts)
    # 必须 compare_digest,普通 == 在长度不等时提前返回,存在时序侧信道
    return hmac.compare_digest(expected, str(signature or "").lower())
