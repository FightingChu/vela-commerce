"""币种。ISO 4217 子集,minor units 按 ISO 定,别拍脑袋加。

JPY 是 0 位小数的坑,报价/对账都吃过亏(#VT-1755),所有舍入必须
先看 currency.minor_units。
"""

from __future__ import annotations

import enum

from vela.config.errors import ValidationError


class CurrencyEnum(str, enum.Enum):
    CNY = "CNY"
    USD = "USD"
    HKD = "HKD"
    JPY = "JPY"
    EUR = "EUR"

    @property
    def minor_units(self) -> int:
        return MINOR_UNITS[self]

    def symbol(self) -> str:
        return _SYMBOLS[self]


MINOR_UNITS: dict[CurrencyEnum, int] = {
    CurrencyEnum.CNY: 2,
    CurrencyEnum.USD: 2,
    CurrencyEnum.HKD: 2,
    CurrencyEnum.EUR: 2,
    CurrencyEnum.JPY: 0,
}

_SYMBOLS: dict[CurrencyEnum, str] = {
    CurrencyEnum.CNY: "¥",
    CurrencyEnum.USD: "$",
    CurrencyEnum.HKD: "HK$",
    CurrencyEnum.JPY: "JP¥",
    CurrencyEnum.EUR: "€",
}

# normalize() 的宽松别名。历史数据里什么写法都有,收宽一点
_ALIASES: dict[str, CurrencyEnum] = {
    "¥": CurrencyEnum.CNY,
    "RMB": CurrencyEnum.CNY,
    "US$": CurrencyEnum.USD,
    "€": CurrencyEnum.EUR,
}


def normalize(code: str) -> CurrencyEnum:
    """宽松解析:"cny" / "CNY" / "¥" 都收,不认识抛 ValueError。"""
    if not isinstance(code, str):
        raise ValueError(f"币种必须是字符串: {code!r}")
    key = code.strip()
    if not key:
        raise ValueError("币种为空")
    upper = key.upper()
    if upper in _ALIASES:
        return _ALIASES[upper]
    if key in _ALIASES:  # 符号类别名区分大小写
        return _ALIASES[key]
    try:
        return CurrencyEnum(upper)
    except ValueError:
        raise ValueError(f"未知币种: {code!r}") from None


def assert_same_currency(a: CurrencyEnum, b: CurrencyEnum) -> None:
    if a is not b:
        raise ValidationError(
            "币种不一致", detail={"left": a.value, "right": b.value}
        )
