"""券计算规则。纯函数,不碰 DB——service/preview 都从这里拿数。

优惠额一律钳在 [0, amount],能算出负数就是事故(参照 pricing/rules.py
的下限保护,#VT-1996 之后所有算钱的地方都加了钳制)。
"""

from __future__ import annotations

from decimal import Decimal

from vela.domain.promotion.coupon_model import CouponKind
from vela.domain.shared import round_half_up, to_decimal

ZERO = Decimal(0)
_ONE = Decimal(1)


class ThresholdRule:
    """满减:amount >= threshold 才给 discount,否则 0。"""

    def __init__(self, threshold, discount):
        self.threshold = to_decimal(threshold)
        self.discount = to_decimal(discount)

    def apply(self, amount) -> Decimal:
        amount = to_decimal(amount)
        if amount < self.threshold:
            return ZERO
        # 门槛达到了但券面额比订单还大,只抵到订单额
        return min(self.discount, amount)


class DiscountRule:
    """折扣:discount_rate 存的是"折扣后比例",0.900 = 九折。

    历史上有一版存的是"减掉的比例",老数据迁移时已经翻过来了,
    运营后台别再配反。
    """

    def __init__(self, rate):
        self.rate = to_decimal(rate)

    def apply(self, amount) -> Decimal:
        amount = to_decimal(amount)
        off = round_half_up(amount * (_ONE - self.rate))
        if off < ZERO:
            return ZERO
        return min(off, amount)


class FlatRule:
    """无门槛直减。"""

    def __init__(self, discount):
        self.discount = to_decimal(discount)

    def apply(self, amount) -> Decimal:
        amount = to_decimal(amount)
        return min(self.discount, amount)


def rule_for(row: dict):
    """工厂:入参是 to_rule_row() 的裸 dict,别直接喂 ORM 对象。"""
    kind = row["kind"]
    if isinstance(kind, str):
        # 报表里还有存量字符串,容错解析(coupon_model.py 顶部说过这事)
        kind = CouponKind(kind)
    if kind is CouponKind.THRESHOLD:
        return ThresholdRule(row["threshold_amount"], row["discount_amount"])
    if kind is CouponKind.DISCOUNT:
        return DiscountRule(row["discount_rate"])
    if kind is CouponKind.NO_THRESHOLD:
        return FlatRule(row["discount_amount"])
    raise ValueError(f"未知券类型: {kind!r}")


def apply_coupon(coupon_row: dict, amount) -> Decimal:
    """单张券对 amount 的优惠额,范围 [0, amount]。"""
    return rule_for(coupon_row).apply(amount)
