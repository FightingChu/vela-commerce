"""券主数据管理。建券/停启用/名单查询,纯 admin 域,不碰核销。

核销在 promotion_ops.py(CouponService),别从这里绕过去动 quota。
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy.orm import Session

from vela.config.errors import ValidationError
from vela.config.logging import get_logger
from vela.domain.promotion import CouponKind, CouponRepository
from vela.domain.promotion.coupon_model import CouponModel
from vela.service import audit_bridge, validation
from vela.service.converters import dt_to_iso, money

log = get_logger(__name__)


def create_coupon(
    session: Session,
    *,
    code: str,
    title: str,
    kind: str,
    total_quota: int,
    threshold_amount="0",
    discount_amount="0",
    discount_rate="1.000",
    per_customer_limit: int = 1,
    valid_from: dt.datetime | None = None,
    valid_to: dt.datetime | None = None,
    stackable: bool = False,
    operator: str | None = None,
) -> CouponModel:
    """建券模板。kind 必须是 CouponKind 三值之一(GIFT/FREE_SHIPPING
    是 2025Q1 下掉的历史遗留,别再往回加)。"""
    code = validation.require_non_empty_str(code, "code")
    title = validation.require_non_empty_str(title, "title")
    validation.require_positive_int(total_quota, "total_quota", allow_zero=False)
    validation.require_positive_int(per_customer_limit, "per_customer_limit", allow_zero=False)

    try:
        kind_val = CouponKind(kind)
    except ValueError:
        raise ValidationError(
            f"非法券类型: {kind!r}", detail={"allowed": [k.value for k in CouponKind]}
        ) from None

    if valid_from and valid_to and valid_from > valid_to:
        raise ValidationError("valid_from 晚于 valid_to")

    coupon = CouponModel(
        code=code,
        title=title,
        kind=kind_val,
        threshold_amount=validation.require_money(threshold_amount, "threshold_amount"),
        discount_amount=validation.require_money(discount_amount, "discount_amount"),
        discount_rate=validation.require_money(discount_rate, "discount_rate"),
        stackable=stackable,
        total_quota=total_quota,
        per_customer_limit=per_customer_limit,
        valid_from=valid_from,
        valid_to=valid_to,
        enabled=True,
    )
    session.add(coupon)
    try:
        session.flush()
    except Exception:
        # code 唯一键冲突最常见,提示给足
        raise ValidationError(f"券 code 已存在: {code}") from None

    audit_bridge.record_admin_action(
        session,
        action="coupon.created",
        target_type="coupon",
        target_id=code,
        detail={"kind": kind_val.value, "total_quota": total_quota, "operator": operator},
    )
    return coupon


def set_enabled(
    session: Session,
    code: str,
    enabled: bool,
    *,
    operator: str | None = None,
    reason: str = "",
) -> CouponModel:
    """停启用。停用挡新核销,已发出去的券到核销时会被
    CouponService._check_usable 拦(报 disabled),不追回。"""
    coupon = CouponRepository(session).get_by_code(code)
    if coupon is None:
        raise ValidationError(f"券不存在: {code}")
    coupon.enabled = bool(enabled)
    session.flush()
    audit_bridge.record_admin_action(
        session,
        action="coupon.enabled" if enabled else "coupon.disabled",
        target_type="coupon",
        target_id=code,
        detail={"reason": reason, "operator": operator},
    )
    log.info("coupon_toggled", code=code, enabled=enabled, operator=operator)
    return coupon


def list_valid(session: Session, at: dt.datetime | None = None) -> list[dict]:
    """当前可领可用的券名单(运营后台首页那块)。"""
    rows = CouponRepository(session).list_valid(at)
    return [
        {
            "code": c.code,
            "title": c.title,
            "kind": c.kind.value if hasattr(c.kind, "value") else str(c.kind),
            "remaining_quota": c.remaining_quota,
            "valid_from": dt_to_iso(c.valid_from),
            "valid_to": dt_to_iso(c.valid_to),
            "discount_amount": money(c.discount_amount),
        }
        for c in rows
    ]
