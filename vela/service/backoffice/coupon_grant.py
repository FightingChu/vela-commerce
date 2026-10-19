"""定向发券。把一张母券按客户克隆成一人一张的定向券。

为什么不直接发母券:quota 是共享池,定向名单没法约束;克隆成
per_customer_limit=1、total_quota=1 的子券,核销路径完全复用,
运营在后台也能按 code 追每个人的用没不用。
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy.orm import Session

from vela.config.errors import ValidationError
from vela.config.logging import get_logger
from vela.domain.promotion import CouponRepository
from vela.domain.promotion.coupon_model import CouponModel
from vela.service import audit_bridge

log = get_logger(__name__)

_SERIAL = 0  # 模块级递增,进程内唯一;多实例靠 code 唯一键兜撞


def grant_to_customers(
    session: Session,
    code: str,
    customer_ids: list[int],
    *,
    operator: str | None = None,
    valid_days: int | None = None,
) -> list[str]:
    """给名单内每人克隆一张子券,返回生成的 code 列表。

    valid_days 给了就按 now + days 设有效期,没给沿用母券窗口
    (母券窗口可能已经关了,那样子券一落地就是过期态,调用方注意)。
    """
    global _SERIAL
    if not customer_ids:
        raise ValidationError("发券名单不能为空")

    mother = CouponRepository(session).get_by_code(code)
    if mother is None:
        raise ValidationError(f"母券不存在: {code}")
    if not mother.enabled:
        raise ValidationError(f"母券已停用: {code}")

    valid_to = None
    if valid_days is not None:
        if valid_days <= 0:
            raise ValidationError(f"valid_days 必须为正: {valid_days}")
        valid_to = dt.datetime.now(tz=dt.timezone.utc) + dt.timedelta(days=valid_days)

    granted: list[str] = []
    for customer_id in customer_ids:
        _SERIAL += 1
        child_code = f"{code}-G{customer_id}X{_SERIAL % 10000}"
        child = CouponModel(
            code=child_code,
            title=f"{mother.title}(定向)",
            kind=mother.kind,
            threshold_amount=mother.threshold_amount,
            discount_amount=mother.discount_amount,
            discount_rate=mother.discount_rate,
            stackable=mother.stackable,
            total_quota=1,
            used_quota=0,
            per_customer_limit=1,
            valid_from=mother.valid_from,
            valid_to=valid_to or mother.valid_to,
            enabled=True,
        )
        session.add(child)
        granted.append(child_code)

    session.flush()
    audit_bridge.record_admin_action(
        session,
        action="coupon.granted",
        target_type="coupon",
        target_id=code,
        detail={
            "count": len(granted),
            "customer_ids": customer_ids[:50],
            "operator": operator,
        },
    )
    log.info("coupon_granted", mother=code, count=len(granted), operator=operator)
    return granted
