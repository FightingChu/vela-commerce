"""金额运算工具。全部基于 Decimal,币种信息由调用方自己保证一致。

舍入规则与 pricing/currency.py 的口径对应关系见 #VT-2031。
"""

from __future__ import annotations

import decimal
from decimal import ROUND_HALF_UP, Decimal

ZERO = Decimal(0)
CENT = Decimal("0.01")

_CTX_QUICK = decimal.Context(prec=28, rounding=ROUND_HALF_UP)


def to_decimal(value) -> Decimal:
    """宽松转换:str/int/float 都收,float 会被显式拒绝(精度坑)。"""
    if isinstance(value, Decimal):
        return value
    if isinstance(value, bool):
        raise ValueError("bool 不是合法金额")
    if isinstance(value, int):
        return Decimal(value)
    if isinstance(value, str):
        try:
            return Decimal(value)
        except decimal.InvalidOperation:
            raise ValueError(f"无法解析为金额: {value!r}") from None
    raise TypeError(f"不支持的金额类型: {type(value).__name__}")


def round_half_up(amount: Decimal, places: int = 2) -> Decimal:
    if places < 0:
        raise ValueError(f"places 不能为负: {places}")
    q = Decimal(1).scaleb(-places)
    return amount.quantize(q, rounding=ROUND_HALF_UP, context=_CTX_QUICK)


def sum_amounts(*amounts) -> Decimal:
    if not amounts:
        return ZERO
    total = ZERO
    for a in amounts:
        total += to_decimal(a)
    return total


def allocate_pro_rata(total: Decimal, weights) -> list[Decimal]:
    """按权重切分 total,余数给最后一个非零份额,保证合计严格相等。"""
    total = to_decimal(total)
    weight_values = [to_decimal(w) for w in weights]
    if not weight_values:
        raise ValueError("weights 不能为空")
    weight_sum = sum_amounts(*weight_values)
    if weight_sum <= 0:
        raise ValueError("权重合计必须为正")
    parts = []
    running = ZERO
    for w in weight_values[:-1]:
        part = round_half_up(total * w / weight_sum)
        parts.append(part)
        running += part
    parts.append(total - running)
    return parts


def max_of(*amounts) -> Decimal:
    if not amounts:
        raise ValueError("至少给一个金额")
    return max(to_decimal(a) for a in amounts)


def min_of(*amounts) -> Decimal:
    if not amounts:
        raise ValueError("至少给一个金额")
    return min(to_decimal(a) for a in amounts)
