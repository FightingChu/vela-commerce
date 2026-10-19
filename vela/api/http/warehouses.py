"""仓库。没有独立主数据表,先从库存台账聚合 distinct 仓库,
等 WMS 对接(#VT-2230)再换成正经档案接口。"""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from vela.api.middleware import db
from vela.config.errors import NotFoundError
from vela.domain.inventory.stock_model import StockModel

bp = Blueprint("warehouses", __name__, url_prefix="/api/v1/warehouses")


@bp.get("")
def list_warehouses():
    from sqlalchemy import func, select

    rows = db().execute(select(StockModel.warehouse).distinct().order_by(StockModel.warehouse)).all()
    return jsonify({"items": [r[0] for r in rows]})


@bp.get("/<warehouse>/stock")
def warehouse_stock(warehouse: str):
    from sqlalchemy import select

    from vela.db.pagination import paginate

    offset = request.args.get("offset", 0, type=int)
    limit = request.args.get("limit", type=int)
    stmt = select(StockModel).where(StockModel.warehouse == warehouse).order_by(StockModel.sku_id)
    page = paginate(db(), stmt, offset=offset, limit=limit)
    if page.total == 0:
        # 没有任何库存记录也谈不上仓库存在,直接 404,客户端少一层判断
        raise NotFoundError(f"仓库 {warehouse} 无库存记录", detail={"warehouse": warehouse})
    items = [
        {"sku_id": s.sku_id, "on_hand": s.on_hand, "reserved": s.reserved, "available": s.available}
        for s in page.items
    ]
    return jsonify({"warehouse": warehouse, "items": items,
                    "total": page.total, "offset": page.offset, "limit": page.limit})
