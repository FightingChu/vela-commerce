"""促销域。import 本包即注册全部表到 Base.metadata。"""

from __future__ import annotations

from vela.domain.promotion import events, preview, rules, stacking
from vela.domain.promotion.coupon_model import CouponKind, CouponModel
from vela.domain.promotion.errors import (
    CouponExhaustedError,
    CouponUnavailableError,
    QuotaExceededError,
)
from vela.domain.promotion.events import (
    EVENT_COUPON_REDEEMED,
    EVENT_COUPON_RELEASED,
    make_coupon_redeemed,
    make_coupon_released,
)
from vela.domain.promotion.preview import checkout_preview
from vela.domain.promotion.redemption_model import CouponRedemptionModel
from vela.domain.promotion.repository import CouponRepository, RedemptionRepository
from vela.domain.promotion.rules import (
    DiscountRule,
    FlatRule,
    ThresholdRule,
    apply_coupon,
    rule_for,
)
from vela.domain.promotion.service import CouponService
from vela.domain.promotion.stacking import best_single, combine_stack, stack_allowed

__all__ = [
    "CouponKind",
    "CouponModel",
    "CouponRedemptionModel",
    "CouponRepository",
    "RedemptionRepository",
    "CouponService",
    "ThresholdRule",
    "DiscountRule",
    "FlatRule",
    "apply_coupon",
    "rule_for",
    "best_single",
    "stack_allowed",
    "combine_stack",
    "checkout_preview",
    "CouponUnavailableError",
    "CouponExhaustedError",
    "QuotaExceededError",
    "EVENT_COUPON_REDEEMED",
    "EVENT_COUPON_RELEASED",
    "make_coupon_redeemed",
    "make_coupon_released",
    "events",
    "rules",
    "stacking",
    "preview",
]
