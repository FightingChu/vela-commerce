"""券主数据。核销在 coupon_redemptions.py,这边只管建档和查询。"""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from vela.api.middleware import db
from vela.api.schemas import CouponCreate
from vela.db import not_deleted
from vela.db.pagination import paginate
from vela.domain.promotion.coupon_model import CouponKind, CouponModel

bp = Blueprint("coupons", __name__, url_prefix="/api/v1/coupons")


def _view(c: CouponModel) -> dict:
    return {
        "code": c.code,
        "title": c.title,
        "kind": getattr(c.kind, "value", str(c.kind)),
        "stackable": c.stackable,
        "total_quota": c.total_quota,
        "used_quota": c.used_quota,
        "remaining_quota": c.remaining_quota,
        "enabled": c.enabled,
    }


@bp.post("")
def create_coupon():
    payload = CouponCreate.model_validate(request.get_json(silent=True) or {})
    coupon = CouponModel(
        code=payload.code,
        title=payload.title,
        kind=CouponKind(payload.kind),
        threshold_amount=payload.threshold_amount,
        discount_amount=payload.discount_amount,
        discount_rate=payload.discount_rate,
        stackable=payload.stackable,
        total_quota=payload.total_quota,
        per_customer_limit=payload.per_customer_limit,
        valid_from=payload.valid_from,
        valid_to=payload.valid_to,
    )
    db().add(coupon)
    db().commit()
    return jsonify(_view(coupon)), 201


@bp.get("")
def list_coupons():

    offset = request.args.get("offset", 0, type=int)
    limit = request.args.get("limit", type=int)
    stmt = not_deleted(CouponModel).order_by(CouponModel.id.desc())
    page = paginate(db(), stmt, offset=offset, limit=limit)
    return jsonify({"items": [_view(c) for c in page.items],
                    "total": page.total, "offset": page.offset, "limit": page.limit})


@bp.get("/<code>")
def get_coupon(code: str):
    coupon = _CouponRepository(db()).get_by_code(code)
    if coupon is None:
        from vela.config.errors import NotFoundError

        raise NotFoundError(f"券不存在: {code}", detail={"code": code})
    return jsonify(_view(coupon))


class _CouponRepository:
    """get_by_code 的薄壳。放 handler 文件里是因为只有这里用,
    挪进 domain/promotion/repository.py 会被重构分支的 merge 冲。"""

    def __init__(self, session):
        from vela.domain.promotion.repository import CouponRepository

        self._repo = CouponRepository(session)

    def get_by_code(self, code: str):
        return self._repo.get_by_code(code)
