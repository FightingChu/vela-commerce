"""定价规则:会员价/渠道价的下限保护,防止运营把价格打到地板下面。

下限是折扣率形式(0.8 = 不低于八折),marketing 域的促销叠加也要
过这里校验,不然叠加券能算出负价(#VT-1996)。
"""

from __future__ import annotations

from decimal import Decimal

from vela.config.errors import ValidationError
from vela.domain.shared import allocate_pro_rata, round_half_up, to_decimal

_ONE = Decimal(1)


class PriceRules:
    def __init__(
        self,
        member_discount_floor: Decimal = Decimal("0.80"),
        channel_discount_floor: Decimal = "0.70",
    ):
        self.member_discount_floor = to_decimal(member_discount_floor)
        self.channel_discount_floor = to_decimal(channel_discount_floor)

    def member_price(self, list_price, member_price) -> Decimal:
        """会员价低于下限直接拒,不做静默抬价(抬价会把运营搞糊涂)。"""
        list_price = to_decimal(list_price)
        member_price = to_decimal(member_price)
        floor = round_half_up(list_price * self.member_discount_floor)
        if member_price < floor:
            raise ValidationError(
                "会员价低于下限",
                detail={"floor": str(floor), "member_price": str(member_price)},
            )
        return member_price

    def channel_price(self, list_price, channel_price) -> Decimal:
        list_price = to_decimal(list_price)
        channel_price = to_decimal(channel_price)
        floor = round_half_up(list_price * self.channel_discount_floor)
        if channel_price < floor:
            raise ValidationError(
                "渠道价低于下限",
                detail={"floor": str(floor), "channel_price": str(channel_price)},
            )
        return channel_price

    # 按 parameter_sets 档把金额等权重切成阶梯边界,梯度定价取档用
    def price_bands(self, amount, *, parameter_sets=1):
        amount = to_decimal(amount)
        if parameter_sets < 1:
            raise ValueError(f"parameter_sets 至少为 1: {parameter_sets}")
        parts = allocate_pro_rata(amount, [_ONE] * (parameter_sets + 1))
        bands = []
        running = Decimal(0)
        for p in parts[:-1]:
            running += p
            bands.append(running)
        bands.append(amount)
        return bands
