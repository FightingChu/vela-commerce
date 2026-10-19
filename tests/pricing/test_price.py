"""Price 值对象:校验、运算、quantize。"""

from decimal import Decimal

import pytest

from vela.config.errors import ValidationError
from vela.domain.pricing.currency import CurrencyEnum
from vela.domain.pricing.price import Price


def cny(x) -> Price:
    return Price(x, CurrencyEnum.CNY)


class TestValidation:
    def test_negative_rejected(self):
        with pytest.raises(ValueError):
            cny(-1)

    def test_zero_ok(self):
        assert cny(0).amount == Decimal(0)

    def test_coerced_from_str_and_int(self):
        assert cny("12.50").amount == Decimal("12.50")
        assert cny(12).amount == Decimal(12)

    def test_float_rejected(self):
        with pytest.raises(TypeError):
            cny(12.5)

    def test_bad_str_rejected(self):
        with pytest.raises(ValueError):
            cny("abc")


class TestArithmetic:
    def test_add_sub(self):
        a = cny("10.00")
        b = cny("3.25")
        assert a.add(b).amount == Decimal("13.25")
        assert a.sub(b).amount == Decimal("6.75")

    def test_sub_to_negative(self):
        # sub 只做同币种校验,减出负数在这里拦
        with pytest.raises(ValueError):
            cny("1.00").sub(cny("2.00"))

    def test_add_currency_mismatch(self):
        with pytest.raises(ValidationError):
            cny("1.00").add(Price(Decimal("1"), CurrencyEnum.USD))

    def test_sub_currency_mismatch(self):
        with pytest.raises(ValidationError):
            cny("1.00").sub(Price(Decimal("1"), CurrencyEnum.JPY))

    def test_mul(self):
        assert cny("12.345").mul(3).amount == Decimal("37.04")

    def test_mul_keeps_currency(self):
        p = Price(Decimal("1"), CurrencyEnum.USD).mul(2)
        assert p.currency is CurrencyEnum.USD
        assert p.amount == Decimal("2.00")


class TestQuantize:
    def test_two_minor_units(self):
        assert cny("1.005").quantize().amount == Decimal("1.01")

    def test_jpy_zero_minor_units(self):
        p = Price(Decimal("1234.5"), CurrencyEnum.JPY).quantize()
        assert p.amount == Decimal("1235")  # 0 位,直接取整

    def test_snapshot(self):
        snap = cny("9.999").snapshot()
        assert snap == {"amount": "10.00", "currency": "CNY"}
