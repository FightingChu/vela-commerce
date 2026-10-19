"""DTO 公共约束。金额一律 str 传输( Decimal 的 json 序列化坑太多,
float 又丢精度),校验只保证"能解析成非负小数",位数不强截,
进域层后由 money_utils.round_half_up 统一。"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Annotated

from pydantic import AfterValidator

from vela.config.errors import ValidationError


def _check_money(v: str) -> str:
    try:
        d = Decimal(v)
    except (InvalidOperation, ValueError):
        raise ValueError(f"金额不是合法小数: {v!r}") from None
    if d < 0:
        raise ValueError(f"金额不能为负: {v!r}")
    return v


Money = Annotated[str, AfterValidator(_check_money)]


def money(value) -> str:
    """域层 Decimal -> API str 的统一出口。"""
    return str(value)
