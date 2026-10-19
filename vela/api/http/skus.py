"""SKU 档案。纯主数据 CRUD,没有业务规则。"""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from vela.api.middleware import db
from vela.api.schemas import SkuCreate
from vela.db import not_deleted
from vela.db.pagination import paginate
from vela.domain.inventory.item_model import SkuModel

bp = Blueprint("skus", __name__, url_prefix="/api/v1/skus")


def _view(s: SkuModel) -> dict:
    return {
        "id": s.id,
        "sku_code": s.sku_code,
        "name": s.name,
        "category": s.category,
        "unit": s.unit,
        "weight_grams": s.weight_grams,
        "is_active": s.is_active,
    }


@bp.post("")
def create_sku():
    payload = SkuCreate.model_validate(request.get_json(silent=True) or {})
    sku = SkuModel(
        sku_code=payload.sku_code,
        name=payload.name,
        category=payload.category,
        unit=payload.unit,
        weight_grams=payload.weight_grams,
        is_active=payload.is_active,
        specs=payload.specs,
    )
    db().add(sku)
    db().commit()
    return jsonify(_view(sku)), 201


@bp.get("")
def list_skus():
    from sqlalchemy import select

    offset = request.args.get("offset", 0, type=int)
    limit = request.args.get("limit", type=int)
    page = paginate(db(), select(SkuModel).order_by(SkuModel.id), offset=offset, limit=limit)
    return jsonify({
        "items": [_view(s) for s in page.items],
        "total": page.total,
        "offset": page.offset,
        "limit": page.limit,
    })


@bp.get("/<int:sku_id>")
def get_sku(sku_id: int):
    # Repository.get 抛 NotFoundError,全局 handler 兜底
    from vela.db.repository import Repository

    sku = Repository(SkuModel)(db()).get(sku_id)
    return jsonify(_view(sku))
