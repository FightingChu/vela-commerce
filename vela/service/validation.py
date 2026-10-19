"""service 层入参校验。domain 里已经有一遍,这里是编排层的最后一道,
给 admin/backoffice 这类"参数来自人工填表"的入口兜底。

校验失败一律 ValidationError(400),别在这里发明新错误类型。
"""

from __future__ import annotations

from decimal import Decimal

from vela.config.errors import ValidationError
from vela.domain.shared import to_decimal


def require_positive_int(value, name: str, *, allow_zero: bool = False) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValidationError(f"{name} 必须是整数,得到: {value!r}")
    if (value < 0) if allow_zero else (value <= 0):
        raise ValidationError(f"{name} 必须为正: {value}")
    return value


def require_non_empty_str(value, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"{name} 不能为空")
    return value.strip()


def require_money(value, name: str, *, allow_zero: bool = True) -> Decimal:
    try:
        amount = to_decimal(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError(f"{name} 不是合法金额: {value!r}({exc})") from None
    if amount < 0 or (amount == 0 and not allow_zero):
        raise ValidationError(f"{name} 不能为负: {amount}")
    return amount


def require_lines(lines) -> list[dict]:
    """下单行最小校验,细的(sku_id 类型/qty 正数)交给 OrderService。"""
    if not lines or not isinstance(lines, list):
        raise ValidationError("订单至少要有一行")
    for idx, raw in enumerate(lines):
        if not isinstance(raw, dict):
            raise ValidationError(f"第 {idx} 行不是对象: {raw!r}")
    return lines


def require_sn(sn, name: str = "order_sn") -> str:
    cleaned = require_non_empty_str(sn, name)
    if len(cleaned) > 24:
        raise ValidationError(f"{name} 超长: {cleaned!r}")
    return cleaned
