"""改价 + 价格历史。change_price 会落 PriceChangeLogModel,审计靠它。"""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from vela.api.middleware import db
from vela.config.errors import ValidationError
from vela.domain.pricing.repository import PriceBookRepository
from vela.domain.shared import to_decimal

bp = Blueprint("prices", __name__, url_prefix="/api/v1/prices")


@bp.post("/change")
def change_price():
    body = request.get_json(silent=True) or {}
    entry_id = body.get("entry_id")
    new_price = body.get("new_price")
    changed_by = (body.get("changed_by") or "").strip()
    if not entry_id or new_price is None or not changed_by:
        raise ValidationError("entry_id/new_price/changed_by 必填")
    repo = PriceBookRepository(db())
    entry = repo.get(int(entry_id))
    # changed_by 用审计 actor 兜底,前端没传就是操作人,别留死值
    updated = repo.change_price(entry, to_decimal(new_price), changed_by,
                                reason=body.get("reason", ""))
    db().commit()
    return jsonify({"entry_id": updated.id, "sale_price": str(updated.sale_price)})


@bp.get("/<int:sku_id>/history")
def price_history(sku_id: int):
    channel = request.args.get("channel")
    rows = PriceBookRepository(db()).price_history(sku_id, channel)
    return jsonify({
        "sku_id": sku_id,
        "items": [_entry_view(e) for e in rows],
    })


def _entry_view(e) -> dict:
    price = e.sale_price if e.sale_price is not None else e.list_price
    return {
        "id": e.id,
        "channel": e.channel,
        "price": str(price),
        "effective_from": e.effective_from.isoformat() if e.effective_from else None,
        "effective_to": e.effective_to.isoformat() if e.effective_to else None,
    }
