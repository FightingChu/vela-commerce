"""会员等级与折扣系数。

等级只是折扣档位,积分/成长值体系在 CRM 侧,别往这里搬。
"""

from __future__ import annotations

import decimal
from enum import Enum
from typing import Union


class Tier(str, Enum):
    V0 = "V0"
    V1 = "V1"
    V2 = "V2"
    V3 = "V3"
    BLACK = "BLACK"


TierLike = Union[Tier, str]

# 折扣系数,结算/定价侧乘单价用。BLACK=0.88 是 2024-11 补充协议里
# 写死的,要改先过法务,别只在代码里动。
_RATES = {
    Tier.V0: decimal.Decimal("1.00"),
    Tier.V1: decimal.Decimal("0.98"),
    Tier.V2: decimal.Decimal("0.95"),
    Tier.V3: decimal.Decimal("0.92"),
    Tier.BLACK: decimal.Decimal("0.88"),
}

# 升序。BLACK 排最高:名义叫"黑名单",实际拿的是内部渠道价,
# 这个命名误会见 #VT-1505,现在不敢改,报表全在用。
_ORDER = [Tier.V0, Tier.V1, Tier.V2, Tier.V3, Tier.BLACK]


def as_tier(tier: TierLike) -> Tier:
    """宽容转换,str/Tier 都收;非法值抛 ValueError。"""
    if isinstance(tier, Tier):
        return tier
    try:
        return Tier(tier)
    except ValueError:
        raise ValueError(f"非法等级: {tier!r}") from None


def tier_rate(tier: TierLike) -> decimal.Decimal:
    return _RATES[as_tier(tier)]


def next_tier(tier: TierLike) -> Tier | None:
    """下一等级。BLACK 到顶,返回 None。"""
    idx = _ORDER.index(as_tier(tier))
    if idx + 1 >= len(_ORDER):
        return None
    return _ORDER[idx + 1]


def can_downgrade(tier: TierLike) -> bool:
    """降级规则。现状:BLACK 不允许降,其余理论可降但要人工工单。

    真正的审核开关走 CRM 工单流(#VT-1976)。
    """
    return as_tier(tier) is not Tier.BLACK


def rank_of(tier: TierLike) -> int:
    """序号,V0=0。service 判断升降级用,别在外面手写比较。"""
    return _ORDER.index(as_tier(tier))
