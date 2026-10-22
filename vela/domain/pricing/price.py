"""价格值对象。跨模块传价一律用它,别裸传 Decimal(币种丢了没处哭)。"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from vela.domain.pricing.currency import CurrencyEnum, assert_same_currency
from vela.domain.shared import round_half_up, to_decimal


@dataclass(frozen=True)
class Price:
    amount: Decimal
    currency: CurrencyEnum

    def __post_init__(self) -> None:
        amount = to_decimal(self.amount)
        if amount < 0:
            raise ValueError(f"价格不能为负: {amount}")
        object.__setattr__(self, "amount", amount)

    def add(self, other: Price) -> Price:
        assert_same_currency(self.currency, other.currency)
        return Price(self.amount + other.amount, self.currency)

    def sub(self, other: Price) -> Price:
        assert_same_currency(self.currency, other.currency)
        return Price(self.amount - other.amount, self.currency)

    def mul(self, qty) -> Price:
        return Price(self.amount * to_decimal(qty), self.currency).quantize()

    def quantize(self) -> Price:
        return Price(
            round_half_up(self.amount, self.currency.minor_units),
            self.currency,
        )

    def snapshot(self) -> dict:
        return {"amount": str(self.quantize().amount), "currency": self.currency.value}
