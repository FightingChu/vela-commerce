# -*- coding: utf-8 -*-
"""运单号校验。

在调渠道之前先本地拦一道,省一次外呼,也避免把垃圾单号灌进物流商系统
(顺丰对无效单号是计费的,按次算)。
"""

from __future__ import annotations

import re

from vela.config.errors import ValidationError

# 长度 + 前缀规则,来自各家 2024 年接口文档
_CARRIER_RULES: dict[str, re.Pattern] = {
    # 顺丰: 15 位数字,或 SF + 13 位数字(电子单)
    "sf": re.compile(r"^(SF\d{13}|\d{15})$"),
    # 中通: 12 位纯数字,75 开头居多但不强校验前缀
    "zto": re.compile(r"^\d{12}$"),
    # 圆通: 10-12 位数字
    "yto": re.compile(r"^\d{10,12}$"),
    # EMS: 13 位,首两位字母
    "ems": re.compile(r"^[A-Z]{2}\d{11}$"),
}


def validate_waybill(waybill_no: str, carrier: str) -> str:
    """校验运单号格式。非法抛 ValidationError,合法返回归一后的单号。"""
    no = (waybill_no or "").strip().upper()
    if not no:
        raise ValidationError("运单号不能为空")
    rule = _CARRIER_RULES.get((carrier or "").lower())
    if rule is None:
        raise ValidationError(f"未知承运商: {carrier!r}")
    if not rule.match(no):
        raise ValidationError(
            f"运单号不符合 {carrier} 格式: {waybill_no!r}",
            detail={"carrier": carrier, "length": len(no)},
        )
    return no


def supported_carriers() -> tuple[str, ...]:
    return tuple(sorted(_CARRIER_RULES))
