"""过期券下架。每天 00:05 跑,踩在日切后第一批。

下架是置 enabled=False,不删行:券的核销记录、报表口径都挂
coupon_id,删了历史就断了。真要清理走 DBA 的归档流程。
"""

from __future__ import annotations

from sqlalchemy import select

from vela.config.clocks import utc_now
from vela.domain.promotion.coupon_model import CouponModel
from vela.jobs import context
from vela.jobs.registry import register_job


@register_job("coupon_expire", trigger="每天 00:05")
def run(session=None) -> dict:
    with context.job_session(session) as s:
        now = utc_now()
        stmt = (
            select(CouponModel)
            .where(
                CouponModel.enabled.is_(True),
                CouponModel.valid_to.is_not(None),
                CouponModel.valid_to < now,
            )
            .order_by(CouponModel.id)
        )
        rows = s.execute(stmt).scalars().all()
        for coupon in rows:
            coupon.enabled = False

    return {"expired": len(rows)}
