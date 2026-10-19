"""价格册。条目查询 + 新建;改价不在这,在 prices.py(带变更日志)。"""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from vela.api.middleware import db
from vela.api.schemas import PriceEntryIn
from vela.config.errors import ValidationError
from vela.db import not_deleted
from vela.db.pagination import paginate
from vela.domain.pricing.models import PriceBookEntryModel
from vela.domain.pricing.repository import PriceBookRepository
from vela.domain.shared import to_decimal

bp = Blueprint("pricebook", __name__, url_prefix="/api/v1/pricebook")


def _view(e: PriceBookEntryModel) -> dict:
    return {
        "id": e.id,
        "sku_id": e.sku_id,
        "list_price": str(e.list_price),
        "sale_price": str(e.sale_price) if e.sale_price is not None else None,
        "currency": e.currency,
        "channel": e.channel,
        "effective_from": e.effective_from.isoformat() if e.effective_from else None,
        "effective_to": e.effective_to.isoformat() if e.effective_to else None,
    }


@bp.get("")
def list_entries():
    from sqlalchemy import select

    sku_id = request.args.get("sku_id", type=int)
    channel = request.args.get("channel")
    offset = request.args.get("offset", 0, type=int)
    limit = request.args.get("limit", type=int)
    stmt = not_deleted(PriceBookEntryModel)
    if sku_id:
        stmt = stmt.where(PriceBookEntryModel.sku_id == sku_id)
    if channel:
        stmt = stmt.where(PriceBookEntryModel.channel == channel)
    stmt = stmt.order_by(PriceBookEntryModel.effective_from.desc())
    page = paginate(db(), stmt, offset=offset, limit=limit)
    return jsonify({"items": [_view(e) for e in page.items],
                    "total": page.total, "offset": page.offset, "limit": page.limit})


@bp.post("")
def create_entry():
    payload = PriceEntryIn.model_validate(request.get_json(silent=True) or {})
    if payload.effective_to and payload.effective_to <= payload.effective_from:
        raise ValidationError("effective_to 必须晚于 effective_from")
    entry = PriceBookEntryModel(
        sku_id=payload.sku_id,
        list_price=to_decimal(payload.list_price),
        sale_price=to_decimal(payload.sale_price) if payload.sale_price else None,
        currency=payload.currency,
        channel=payload.channel,
        effective_from=payload.effective_from,
        effective_to=payload.effective_to,
    )
    db().add(entry)
    db().commit()
    return jsonify(_view(entry)), 201


@bp.get("/current")
def current_price():
    sku_id = request.args.get("sku_id", type=int)
    if not sku_id:
        raise ValidationError("sku_id 必填")
    channel = request.args.get("channel", "")
    entry = PriceBookRepository(db()).current_price(sku_id, channel)
    if entry is None:
        from vela.config.errors import NotFoundError

        raise NotFoundError(f"sku {sku_id} 在渠道 {channel!r} 无生效价",
                            detail={"sku_id": sku_id, "channel": channel})
    return jsonify(_view(entry))
