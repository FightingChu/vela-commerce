"""短信场景的手机号脱敏。

为什么不 import vela.domain.customer.phone:日志脱敏是横切关注点,
integrations 不该依赖 domain(方向反了)。规则保持一致:
138****5678,带 _MASKED_MARK 判断。两边哪天分叉了以 domain 为准。
"""

from __future__ import annotations

import re

_MASKED_MARK = "****"

# 1 开头 11 位,宽松匹配正文里的手机号
_PHONE_RE = re.compile(r"(?<!\d)(1\d{10})(?!\d)")


def mask(phone: str) -> str:
    """13812345678 -> 138****5678。非 11 位原样打码中间段,不抛(日志场景要稳)。"""
    if not phone:
        return ""
    s = "".join(phone.split())
    if len(s) == 11 and s.isdigit():
        return s[:3] + _MASKED_MARK + s[-4:]
    # 长度不对的脏数据,至少把中间打掉,别整个输出
    if len(s) >= 8:
        return s[:3] + _MASKED_MARK + s[-2:]
    return _MASKED_MARK


def is_masked(phone: str | None) -> bool:
    return bool(phone) and _MASKED_MARK in phone


def mask_in_text(text: str) -> str:
    """把一段文本里出现的手机号整体打码,发给渠道前的日志用这个。"""
    if not text:
        return text
    return _PHONE_RE.sub(lambda m: mask(m.group(1)), text)
