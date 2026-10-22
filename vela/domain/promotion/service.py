"""核销/退券编排。调用方自己管事务(session 由外部传入或取 current_session)。

幂等策略:第一优先是 redemption 表的 (coupon_id, customer_id, order_sn)
唯一键,token 幂等键只作为网关层的辅助标记——真正的重试去重看订单号。
"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy.orm import Session

from vela.config.clocks import utc_now
from vela.config.logging import get_logger
from vela.db import current_session
from vela.domain.promotion import events as ev
from vela.domain.promotion.coupon_model import CouponModel
from vela.domain.promotion.errors import (
    CouponExhaustedError,
    CouponUnavailableError,
    QuotaExceededError,
)
from vela.domain.promotion.redemption_model import CouponRedemptionModel
from vela.domain.promotion.repository import CouponRepository, RedemptionRepository
from vela.domain.promotion.rules import apply_coupon
from vela.domain.shared import build_key, normalize_token, to_decimal

# #VT-2217 幂等键没带 scope 是历史事故,别学——现在统一 scope:token 格式,
# 老网关重试不带 token(发 "-1")时 normalize 后为空,退回用 order_sn 兜底。
IDEM_SCOPE = "coupon_redeem"

log = get_logger(__name__)


def _idem_key(token, order_sn: str) -> str:
    token = normalize_token(token)
    if not token:
        token = order_sn
    return build_key(IDEM_SCOPE, token)


class CouponService:
    def __init__(self, session: Session | None = None):
        self.session = session or current_session()

    # ---- 读侧帮助,给下单前校验用 ----

    def coupon_by_code(self, code: str) -> CouponModel | None:
        return CouponRepository(self.session).get_by_code(code)

    # ---- 核销 ----

    def redeem(
        self,
        code: str,
        customer_id: str,
        order_sn: str,
        amount,
        *,
        token: str | None = None,
    ) -> Decimal:
        """核销一张券,返回实抵金额。重试同单同券直接返回上次结果。"""
        amount = to_decimal(amount)
        coupons = CouponRepository(self.session)
        redemptions = RedemptionRepository(self.session)

        coupon = coupons.get_by_code(code)
        if coupon is None:
            raise CouponUnavailableError(
                f"券不存在: {code}", detail={"reason": "not_found", "code": code}
            )

        # 幂等:同 order_sn+coupon 已核销过,原样返回上次结果,不再动 quota
        existing = redemptions.find_by_order(order_sn, coupon_id=coupon.id)
        if existing:
            log.info(
                "coupon_redeem_idempotent_hit",
                code=code,
                order_sn=order_sn,
                idem_key=_idem_key(token, order_sn),
            )
            return existing[0].discount_taken

        self._check_usable(coupon)
        if coupon.remaining_quota <= 0:
            raise CouponExhaustedError(
                f"券 {code} 总量已发完", detail={"code": code}
            )
        if redemptions.count_by_customer(coupon.id, customer_id) >= coupon.per_customer_limit:
            raise QuotaExceededError(
                f"客户 {customer_id} 领用券 {code} 超过上限 {coupon.per_customer_limit}",
                detail={"code": code, "limit": coupon.per_customer_limit},
            )

        discount = apply_coupon(coupon.to_rule_row(), amount)
        if discount <= 0:
            raise CouponUnavailableError(
                f"券 {code} 未达门槛或无优惠",
                detail={"reason": "no_benefit", "code": code, "amount": str(amount)},
            )

        coupon.used_quota += 1
        row = redemptions.record(
            coupon.id, customer_id, order_sn, discount, redeemed_at=utc_now()
        )
        self.session.flush()
        self.session.info.setdefault("vela_events", []).append(
            ev.make_coupon_redeemed(
                coupon_code=code,
                customer_id=customer_id,
                order_sn=order_sn,
                discount_taken=discount,
            )
        )
        log.info(
            "coupon_redeemed",
            code=code,
            order_sn=order_sn,
            customer_id=customer_id,
            discount=str(discount),
            idem_key=_idem_key(token, order_sn),
        )
        return row.discount_taken

    def _check_usable(self, coupon: CouponModel, at=None) -> None:
        at = at or utc_now()
        if not coupon.enabled:
            raise CouponUnavailableError(
                f"券 {coupon.code} 已停用",
                detail={"reason": "disabled", "code": coupon.code},
            )
        if coupon.valid_from is not None and at < coupon.valid_from:
            raise CouponUnavailableError(
                f"券 {coupon.code} 未到生效时间",
                detail={"reason": "not_started", "code": coupon.code},
            )
        if coupon.valid_to is not None and at > coupon.valid_to:
            raise CouponUnavailableError(
                f"券 {coupon.code} 已过期",
                detail={"reason": "expired", "code": coupon.code},
            )

    # ---- 退券 ----

    def release(self, order_sn: str) -> list[CouponRedemptionModel]:
        """整单退券:quota 回退、删核销行、发 released 事件。

        没有核销记录时返回空列表(退券幂等,不报错)。
        """
        coupons = CouponRepository(self.session)
        redemptions = RedemptionRepository(self.session)
        rows = list(redemptions.find_by_order(order_sn))
        for row in rows:
            coupon = coupons.get(row.coupon_id, include_deleted=True)
            if coupon.used_quota > 0:
                coupon.used_quota -= 1
            redemptions.delete(row)  # 无软删 mixin,物理删
            self.session.info.setdefault("vela_events", []).append(
                ev.make_coupon_released(
                    coupon_code=coupon.code,
                    customer_id=row.customer_id,
                    order_sn=order_sn,
                    discount_returned=row.discount_taken,
                )
            )
            log.info(
                "coupon_released",
                code=coupon.code,
                order_sn=order_sn,
                customer_id=row.customer_id,
                discount=str(row.discount_taken),
            )
        if rows:
            self.session.flush()
        return rows
