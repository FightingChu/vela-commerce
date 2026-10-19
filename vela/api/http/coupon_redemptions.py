"""券核销/回退。redeem 的幂等和限额校验全在 CouponService,这里不重复。"""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from vela.api.middleware import db
from vela.config.errors import ValidationError
from vela.domain.promotion.service import CouponService
from vela.domain.shared import to_decimal

bp = Blueprint("coupon_redemptions", __name__, url_prefix="/api/v1/coupon-redemptions")


@bp.post("")
def redeem():
    body = request.get_json(silent=True) or {}
    code = (body.get("code") or "").strip()
    customer_id = body.get("customer_id")
    order_sn = (body.get("order_sn") or "").strip()
    amount = body.get("amount")
    if not code or not customer_id or not order_sn or amount is None:
        raise ValidationError("code/customer_id/order_sn/amount 必填")
    discount = CouponService(db()).redeem(
        code, str(customer_id), order_sn, to_decimal(amount),
        token=body.get("token"),
    )
    db().commit()
    return jsonify({"code": code, "order_sn": order_sn, "discount_taken": str(discount)}), 201


@bp.post("/release")
def release():
    body = request.get_json(silent=True) or {}
    order_sn = (body.get("order_sn") or "").strip()
    if not order_sn:
        raise ValidationError("order_sn 必填")
    rows = CouponService(db()).release(order_sn)
    db().commit()
    return jsonify({"order_sn": order_sn, "released": len(rows)})


@bp.get("")
def list_redemptions():
    from sqlalchemy import select

    from vela.db.pagination import paginate
    from vela.domain.promotion.redemption_model import CouponRedemptionModel

    offset = request.args.get("offset", 0, type=int)
    limit = request.args.get("limit", type=int)
    stmt = select(CouponRedemptionModel).order_by(CouponRedemptionModel.id.desc())
    coupon_id = request.args.get("coupon_id", type=int)
    if coupon_id:
        stmt = stmt.where(CouponRedemptionModel.coupon_id == coupon_id)
    page = paginate(db(), stmt, offset=offset, limit=limit)
    items = [
        {
            "id": r.id,
            "coupon_id": r.coupon_id,
            "customer_id": r.customer_id,
            "order_sn": r.order_sn,
            "discount_taken": str(r.discount_taken),
        }
        for r in page.items
    ]
    return jsonify({"items": items, "total": page.total, "offset": page.offset, "limit": page.limit})
