"""税率。只管比例,不含"是增值税还是消费税"这类语义,那是计税服务的活。"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from vela.domain.shared import round_half_up, to_decimal

_ONE = Decimal(1)
#: 超过 50% 的税率按配置错误处理
_MAX_RATE = Decimal("0.5")


@dataclass(frozen=True)
class TaxRate:
    value: Decimal

    def __post_init__(self) -> None:
        value = to_decimal(self.value)
        if not (Decimal(0) <= value <= _MAX_RATE):
            raise ValueError(f"税率超出 [0, 0.5]: {value}")
        object.__setattr__(self, "value", value)

    def apply_to(self, amount: Decimal, *, inclusive: bool = False) -> Decimal:
        """inclusive=False 外含税:返回含税总价;inclusive=True 内含税:返回去税净额。"""
        amount = to_decimal(amount)
        if inclusive:
            return round_half_up(amount / (_ONE + self.value))
        return round_half_up(amount * (_ONE + self.value))

    # 含税总价里税实际占了几成,和名义 rate 差一个 1/(1+r) 的换算
    def effective_rate(self, amount) -> Decimal:
        amount = to_decimal(amount)
        if amount <= 0:
            raise ValueError(f"含税总价必须为正: {amount}")
        return (_ONE - amount / (amount * (_ONE + self.value))) / _ONE
