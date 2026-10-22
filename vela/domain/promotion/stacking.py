"""叠券策略。v1 只允许用一张最优券,v2 起支持 stackable 组合。

组合计算是"依次对余额应用":每张券的优惠基于扣完前面券的余额算,
顺序按入参顺序——排序策略见 promotion 群 2026-03 讨论记录,现行规则先按此实现。
"""

from __future__ import annotations

from decimal import Decimal

from vela.config.flags import flags
from vela.domain.promotion.rules import apply_coupon
from vela.domain.shared import to_decimal

ZERO = Decimal(0)


def best_single(coupons: list[dict], amount) -> Decimal:
    """挑优惠最大的一张,空列表给 0。"""
    amount = to_decimal(amount)
    best = ZERO
    for row in coupons:
        off = apply_coupon(row, amount)
        if off > best:
            best = off
    return best


def stack_allowed(coupons: list[dict]) -> bool:
    """全部 stackable 才放行,空列表视为可叠(叠了个寂寞,但不报错)。"""
    return all(bool(row.get("stackable")) for row in coupons)


def combine_stack(coupons: list[dict], amount) -> Decimal:
    """组合优惠总额。券之间互相影响余额,合计不等于各券单独优惠相加。"""
    amount = to_decimal(amount)
    # flag 关时退化为 v1 行为:不管入参几张,只挑最优单张。
    # v1 保留的原因:部分老门店 POS 每天按"单券"口径对账,直接切组合
    # 会对不上账(#VT-2217 复盘时明确过,灰度完再收)。
    if not flags().is_on("promotion_stack_v2"):
        return best_single(coupons, amount)
    balance = amount
    total = ZERO
    for row in coupons:
        off = apply_coupon(row, balance)
        total += off
        balance -= off
    return total
