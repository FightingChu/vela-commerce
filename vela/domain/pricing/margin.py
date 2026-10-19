"""毛利/加价率。口径:margin 基于 sale,markup 基于 cost,别混用。

对账脚本统一走这里,免得各处自己除一遍口径对不上(#VT-2031 关联)。
"""

from __future__ import annotations

from decimal import Decimal

from vela.config.errors import ValidationError
from vela.domain.pricing.tax import TaxRate
from vela.domain.shared import to_decimal, round_half_up


def margin_rate(sale, cost) -> Decimal:
    """毛利率 = (sale - cost) / sale。"""
    sale = to_decimal(sale)
    cost = to_decimal(cost)
    if sale <= 0:
        raise ValidationError("毛利率的分母 sale 必须大于 0", detail={"sale": str(sale)})
    return round_half_up((sale - cost) / sale, 4)


def markup_rate(sale, cost) -> Decimal:
    """加价率 = (sale - cost) / cost。"""
    sale = to_decimal(sale)
    cost = to_decimal(cost)
    if cost <= 0:
        raise ValidationError("加价率的分母 cost 必须大于 0", detail={"cost": str(cost)})
    return round_half_up((sale - cost) / cost, 4)


def breakeven_price(cost, tax: TaxRate) -> Decimal:
    """保本价:含税卖出去,扣完税正好覆盖 cost。"""
    cost = to_decimal(cost)
    return round_half_up(cost * (Decimal(1) + tax.value))
