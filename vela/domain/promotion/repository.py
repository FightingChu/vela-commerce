"""券与核销流水的仓储。quota 回退也在 service,这层只管查和插。"""

from __future__ import annotations

import datetime as dt
from typing import Sequence

from sqlalchemy import or_, select

from vela.config.clocks import utc_now
from vela.db import Repository
from vela.domain.promotion.coupon_model import CouponModel
from vela.domain.promotion.redemption_model import CouponRedemptionModel


class CouponRepository(Repository[CouponModel]):
    model = CouponModel

    def get_by_code(self, code: str) -> CouponModel | None:
        stmt = select(CouponModel).where(CouponModel.code == code).limit(1)
        return self.session.execute(self._scoped(stmt)).scalar_one_or_none()

    def list_valid(self, at: dt.datetime | None = None) -> Sequence[CouponModel]:
        """enabled + 窗口内 + 没超发。at 缺省取当前时间。

        注意"没超发"只看 total/used,per_customer_limit 是服务层的事。
        """
        at = at or utc_now()
        stmt = select(CouponModel).where(
            CouponModel.enabled.is_(True),
            or_(CouponModel.valid_from.is_(None), CouponModel.valid_from <= at),
            or_(CouponModel.valid_to.is_(None), CouponModel.valid_to >= at),
            CouponModel.used_quota < CouponModel.total_quota,
        )
        return self.session.execute(self._scoped(stmt)).scalars().all()


class RedemptionRepository(Repository[CouponRedemptionModel]):
    model = CouponRedemptionModel

    def count_by_customer(self, coupon_id: int, customer_id: str) -> int:
        stmt = select(CouponRedemptionModel).where(
            CouponRedemptionModel.coupon_id == coupon_id,
            CouponRedemptionModel.customer_id == customer_id,
        )
        return len(list(self.session.execute(self._scoped(stmt)).scalars()))

    def find_by_order(
        self, order_sn: str, *, coupon_id: int | None = None
    ) -> Sequence[CouponRedemptionModel]:
        stmt = select(CouponRedemptionModel).where(
            CouponRedemptionModel.order_sn == order_sn
        )
        if coupon_id is not None:
            stmt = stmt.where(CouponRedemptionModel.coupon_id == coupon_id)
        return self.session.execute(self._scoped(stmt)).scalars().all()

    def record(
        self,
        coupon_id: int,
        customer_id: str,
        order_sn: str,
        discount_taken,
        redeemed_at: dt.datetime | None = None,
    ) -> CouponRedemptionModel:
        row = CouponRedemptionModel(
            coupon_id=coupon_id,
            customer_id=customer_id,
            order_sn=order_sn,
            discount_taken=discount_taken,
            redeemed_at=redeemed_at or utc_now(),
        )
        return self.add(row)
