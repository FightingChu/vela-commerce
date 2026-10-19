# -*- coding: utf-8 -*-
"""规则与叠券纯逻辑。三种券全分支 + 叠加 flag 开/关两态。"""

from __future__ import annotations

from decimal import Decimal

import pytest

import vela.domain.promotion.coupon_model  # noqa: F401 确保建表
import vela.domain.promotion.redemption_model  # noqa: F401
from vela.domain.promotion.coupon_model import CouponKind
from vela.domain.promotion.rules import (
    DiscountRule,
    FlatRule,
    ThresholdRule,
    apply_coupon,
    rule_for,
)
from vela.domain.promotion.stacking import best_single, combine_stack, stack_allowed
from vela.config.flags import flags

D = Decimal


def _row(kind, **kw):
    base = dict(
        code="T1",
        kind=kind,
        threshold_amount=D("100"),
        discount_amount=D("20"),
        discount_rate=D("0.900"),
        stackable=False,
    )
    base.update(kw)
    return base


class TestThresholdRule:
    def test_below_threshold_is_zero(self):
        assert ThresholdRule("100", "20").apply(D("99.99")) == D("0")

    def test_at_threshold_hits(self):
        # 含等号,运营口径"满100"是 >=
        assert ThresholdRule("100", "20").apply(D("100")) == D("20")

    def test_over_threshold(self):
        assert ThresholdRule("100", "20").apply(D("250")) == D("20")

    def test_discount_capped_at_amount(self):
        # 券面 20 > 订单 12(勉强过 10 的门槛),只抵到订单额
        assert ThresholdRule("10", "20").apply(D("12")) == D("12")


class TestDiscountRule:
    def test_basic_rounding(self):
        # 33.33 * 0.1 = 3.333 -> 3.33
        assert DiscountRule("0.900").apply(D("33.33")) == D("3.33")

    def test_round_half_up(self):
        # 25.00 * 0.1 = 2.500,正好两位,原样
        assert DiscountRule("0.900").apply(D("25.00")) == D("2.50")
        # 32.85 * 0.1 = 3.285,五入 -> 3.29
        assert DiscountRule("0.900").apply(D("32.85")) == D("3.29")

    def test_zero_rate_means_full_off_capped(self):
        assert DiscountRule("0").apply(D("50")) == D("50")

    def test_rate_one_means_nothing_off(self):
        assert DiscountRule("1").apply(D("50")) == D("0")


class TestFlatRule:
    def test_direct_off(self):
        assert FlatRule("8").apply(D("100")) == D("8")

    def test_capped_at_amount(self):
        assert FlatRule("8").apply(D("5")) == D("5")


class TestRuleFor:
    def test_factory_dispatch(self):
        assert isinstance(rule_for(_row(CouponKind.THRESHOLD)), ThresholdRule)
        assert isinstance(rule_for(_row(CouponKind.DISCOUNT)), DiscountRule)
        assert isinstance(rule_for(_row(CouponKind.NO_THRESHOLD)), FlatRule)

    def test_factory_tolerates_legacy_string_kind(self):
        # 报表回流的存量字符串
        assert isinstance(rule_for(_row("THRESHOLD")), ThresholdRule)

    def test_unknown_kind_rejected(self):
        with pytest.raises(ValueError):
            rule_for(_row("GIFT"))

    def test_apply_coupon_matches_rule(self):
        assert apply_coupon(_row(CouponKind.THRESHOLD), D("150")) == D("20")


class TestStackingFlagOff:
    """v1 行为:再能叠也只挑最优单张。"""

    def setup_method(self):
        flags().disable("promotion_stack_v2")

    def test_stack_allowed_requires_all(self):
        a = _row(CouponKind.NO_THRESHOLD, stackable=True)
        b = _row(CouponKind.NO_THRESHOLD, stackable=False)
        assert stack_allowed([a, a]) is True
        assert stack_allowed([a, b]) is False
        assert stack_allowed([]) is True

    def test_combine_degrades_to_best_single(self):
        a = _row(CouponKind.NO_THRESHOLD, discount_amount=D("5"), stackable=True)
        b = _row(CouponKind.NO_THRESHOLD, discount_amount=D("9"), stackable=True)
        # flag 关:即使都可叠,也只给 9 不是 14
        assert combine_stack([a, b], D("100")) == D("9")
        assert combine_stack([a, b], D("100")) == best_single([a, b], D("100"))

    def test_empty_gives_zero(self):
        assert best_single([], D("100")) == D("0")
        assert combine_stack([], D("100")) == D("0")


class TestStackingFlagOn:
    def setup_method(self):
        flags().enable("promotion_stack_v2")

    def test_sequential_balance(self):
        # 先打九折再直减:100 -> 90,再减 10 -> 80,合计优惠 20
        disc = _row(CouponKind.DISCOUNT, discount_rate=D("0.900"), stackable=True)
        flat = _row(CouponKind.NO_THRESHOLD, discount_amount=D("10"), stackable=True)
        assert combine_stack([disc, flat], D("100")) == D("20")

    def test_order_matters_for_total(self):
        # 满减先扣会改变余额,合计与顺序有关,这是按余额叠加的固有语义
        thr = _row(CouponKind.THRESHOLD, threshold_amount=D("50"),
                   discount_amount=D("30"), stackable=True)
        disc = _row(CouponKind.DISCOUNT, discount_rate=D("0.900"), stackable=True)
        # 先减 30 再九折:70*0.1=7,合计 37
        assert combine_stack([thr, disc], D("100")) == D("37")
        # 先九折再减 30:10 + 30 = 40(门槛 50 仍满足,余额 90)
        assert combine_stack([disc, thr], D("100")) == D("40")

    def test_not_stackable_flag_on_still_single(self):
        # flag 开但券没标 stackable,stack_allowed 拦住,combine 不该被直接调
        a = _row(CouponKind.NO_THRESHOLD, discount_amount=D("5"), stackable=False)
        assert stack_allowed([a]) is False


class TestCheckoutPreview:
    def _coupons(self):
        return [
            _row(CouponKind.NO_THRESHOLD, code="A", discount_amount=D("8"), stackable=True),
            _row(CouponKind.NO_THRESHOLD, code="B", discount_amount=D("12"), stackable=True),
        ]

    def test_flag_on_stacked_ge_best(self):
        flags().enable("promotion_stack_v2")
        from vela.domain.promotion import checkout_preview

        r = checkout_preview(self._coupons(), D("100"))
        assert r["best"] == D("12")
        assert r["stacked"] == D("20")

    def test_flag_off_stacked_equals_best(self):
        flags().disable("promotion_stack_v2")
        from vela.domain.promotion import checkout_preview

        r = checkout_preview(self._coupons(), D("100"))
        assert r["best"] == r["stacked"] == D("12")
