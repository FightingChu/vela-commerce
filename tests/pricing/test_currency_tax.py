"""currency / tax 全分支。"""

from decimal import Decimal

import pytest

from vela.config.errors import ValidationError
from vela.domain.pricing.currency import (
    MINOR_UNITS,
    CurrencyEnum,
    assert_same_currency,
    normalize,
)
from vela.domain.pricing.tax import TaxRate


class TestCurrency:
    def test_minor_units(self):
        assert MINOR_UNITS[CurrencyEnum.CNY] == 2
        assert MINOR_UNITS[CurrencyEnum.USD] == 2
        assert MINOR_UNITS[CurrencyEnum.HKD] == 2
        assert MINOR_UNITS[CurrencyEnum.EUR] == 2
        # JPY 无小数位,舍入必须走 0 位
        assert MINOR_UNITS[CurrencyEnum.JPY] == 0

    def test_symbol(self):
        assert CurrencyEnum.CNY.symbol() == "¥"
        assert CurrencyEnum.JPY.symbol() == "JP¥"
        assert CurrencyEnum.USD.symbol() == "$"

    @pytest.mark.parametrize("raw", ["cny", "CNY", "¥", "rmb", " usd "])
    def test_normalize_ok(self, raw):
        assert normalize(raw) in (CurrencyEnum.CNY, CurrencyEnum.USD)

    def test_normalize_lower_jpy(self):
        assert normalize("jpy") is CurrencyEnum.JPY

    @pytest.mark.parametrize("bad", ["XXX", "", "人民币123", None])
    def test_normalize_unknown(self, bad):
        with pytest.raises(ValueError):
            normalize(bad)

    def test_assert_same_ok(self):
        assert_same_currency(CurrencyEnum.CNY, CurrencyEnum.CNY)

    def test_assert_same_mismatch(self):
        with pytest.raises(ValidationError):
            assert_same_currency(CurrencyEnum.CNY, CurrencyEnum.USD)


class TestTaxRate:
    def test_valid(self):
        assert TaxRate("0.13").value == Decimal("0.13")
        assert TaxRate(0).value == Decimal(0)
        assert TaxRate(Decimal("0.5")).value == Decimal("0.5")

    @pytest.mark.parametrize("bad", ["-0.01", "0.51", "1", "-1"])
    def test_out_of_range(self, bad):
        with pytest.raises(ValueError):
            TaxRate(bad)

    def test_bad_type(self):
        with pytest.raises((ValueError, TypeError)):
            TaxRate("abc")
        with pytest.raises(TypeError):
            TaxRate(0.13)  # float 不收

    def test_apply_exclusive(self):
        rate = TaxRate("0.13")
        assert rate.apply_to(Decimal(100)) == Decimal("113.00")
        # 半分进位
        assert rate.apply_to(Decimal("0.05")) == Decimal("0.06")

    def test_apply_inclusive(self):
        rate = TaxRate("0.13")
        assert rate.apply_to(Decimal(113), inclusive=True) == Decimal("100.00")

    def test_apply_zero_rate(self):
        rate = TaxRate(0)
        assert rate.apply_to(Decimal("88.88"), inclusive=True) == Decimal("88.88")

    def test_effective_rate(self):
        rate = TaxRate("0.13")
        # 113 元含税价,名义 13% 外加税,含税口径实际税负 13/113
        assert rate.effective_rate(Decimal(113)) == Decimal(13) / Decimal(113)
