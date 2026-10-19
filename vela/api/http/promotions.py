"""促销试算。promotion 域没有独立主数据(都是券),这层只暴露纯函数试算。"""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from vela.config.errors import ValidationError
from vela.domain.promotion.preview import checkout_preview
from vela.domain.promotion.stacking import best_single
from vela.domain.shared import to_decimal

bp = Blueprint("promotions", __name__, url_prefix="/api/v1/promotions")


@bp.post("/preview")
def preview():
    body = request.get_json(silent=True) or {}
    coupons = body.get("coupons")
    amount = body.get("amount")
    if coupons is None or amount is None:
        raise ValidationError("coupons/amount 必填")
    # 纯函数不落库,不用请求 session
    return jsonify(checkout_preview(coupons, to_decimal(amount)))


@bp.post("/best")
def best():
    """单张最优。选券前端要用,单独开个端点省得解析 preview 的全量结构。"""
    body = request.get_json(silent=True) or {}
    coupons = body.get("coupons")
    amount = body.get("amount")
    if coupons is None or amount is None:
        raise ValidationError("coupons/amount 必填")
    discount = best_single(coupons, to_decimal(amount))
    return jsonify({"best_discount": str(discount)})
