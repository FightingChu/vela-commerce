"""导出。现在是同步 JSON 截断返回,正经异步导出任务在 #VT-1503。

行数上限走 settings.max_export_rows,超了直接 400,不做静默截断,
老版截断坑过财务(#VT-1902),别学。
"""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from vela.api.middleware import db
from vela.config.errors import ValidationError
from vela.config.settings import get_settings
from vela.domain.order.models import OrderModel

bp = Blueprint("exports", __name__, url_prefix="/api/v1/exports")


@bp.get("")
def export_types():
    return jsonify({"items": ["orders"]})


@bp.post("/orders")
def export_orders():
    body = request.get_json(silent=True) or {}
    # TODO: 分页游标切换,#VT-2140
    limit = int(body.get("limit") or get_settings().max_export_rows)
    if limit <= 0 or limit > get_settings().max_export_rows:
        raise ValidationError(
            f"limit 超出上限 {get_settings().max_export_rows}", detail={"limit": limit}
        )
    from sqlalchemy import select

    rows = db().execute(
        select(OrderModel).order_by(OrderModel.id).limit(limit)
    ).scalars().all()
    items = [
        {
            "order_sn": o.order_sn,
            "customer_id": o.customer_id,
            "status": o.status,
            "total_amount": str(o.total_amount),
            "paid_amount": str(o.paid_amount),
            "channel": o.channel,
        }
        for o in rows
    ]
    return jsonify({"type": "orders", "count": len(items), "items": items})
