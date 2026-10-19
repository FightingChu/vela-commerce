"""库存。读走 service 契约(inventory_ops.stock_view),写直接 stock_service。

契约函数 lazy import:service 包没就绪时读端点 502,不拖累整个 app。
"""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from vela.api.middleware import db
from vela.api.schemas import ReservationIn
from vela.config.errors import ExternalServiceError, ValidationError

bp = Blueprint("stock", __name__, url_prefix="/api/v1/stock")


@bp.get("/<int:sku_id>")
def stock_view(sku_id: int):
    try:
        from vela.service import inventory_ops
    except ImportError as exc:
        raise ExternalServiceError("inventory_ops service 未就绪") from exc
    warehouse = request.args.get("warehouse", "MAIN")
    return jsonify(inventory_ops.stock_view(sku_id, warehouse=warehouse))


@bp.get("")
def list_stock():
    from sqlalchemy import select

    from vela.db.pagination import paginate
    from vela.domain.inventory.stock_model import StockModel

    warehouse = request.args.get("warehouse")
    offset = request.args.get("offset", 0, type=int)
    limit = request.args.get("limit", type=int)
    stmt = select(StockModel).order_by(StockModel.sku_id)
    if warehouse:
        stmt = stmt.where(StockModel.warehouse == warehouse)
    page = paginate(db(), stmt, offset=offset, limit=limit)
    items = [
        {
            "sku_id": s.sku_id,
            "warehouse": s.warehouse,
            "on_hand": s.on_hand,
            "reserved": s.reserved,
            "available": s.available,
        }
        for s in page.items
    ]
    return jsonify({"items": items, "total": page.total, "offset": page.offset, "limit": page.limit})


@bp.post("/deduct")
def deduct():
    body = request.get_json(silent=True) or {}
    sku_id = body.get("sku_id")
    qty = body.get("qty")
    ref_sn = (body.get("ref_sn") or "").strip()
    if not sku_id or not qty or not ref_sn:
        raise ValidationError("sku_id/qty/ref_sn 必填")
    from vela.domain.inventory.stock_service import deduct as deduct_stock

    stock, _ledger = deduct_stock(
        int(sku_id), int(qty), ref_sn,
        warehouse=body.get("warehouse", "MAIN"), session=db(),
    )
    db().commit()
    return jsonify({"sku_id": stock.sku_id, "warehouse": stock.warehouse, "on_hand": stock.on_hand})
