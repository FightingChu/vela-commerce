"""订单后台操作。鉴权在网关做,这里默认内网可达,别暴露到公网。"""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from vela.api.middleware import db
from vela.config.errors import ValidationError
from vela.db.pagination import paginate
from vela.domain.order.models import OrderModel

bp = Blueprint("order_admin", __name__, url_prefix="/api/v1/order-admin")


def _view(o: OrderModel) -> dict:
    return {
        "order_sn": o.order_sn,
        "customer_id": o.customer_id,
        "status": o.status,
        "total_amount": str(o.total_amount),
        "channel": o.channel,
    }


@bp.get("")
def list_all():
    # 后台排查用,不按客户过滤;真全量对账走 exports
    offset = request.args.get("offset", 0, type=int)
    limit = request.args.get("limit", type=int)
    from sqlalchemy import select

    page = paginate(db(), select(OrderModel).order_by(OrderModel.id.desc()),
                    offset=offset, limit=limit)
    return jsonify({
        "items": [_view(o) for o in page.items],
        "total": page.total,
        "offset": page.offset,
        "limit": page.limit,
    })


@bp.post("/<order_sn>/cancel")
def cancel(order_sn: str):
    from vela.domain.order.cancel import cancel_order

    body = request.get_json(silent=True) or {}
    reason = (body.get("reason") or "").strip()
    if not reason:
        raise ValidationError("取消必须给 reason")
    order = cancel_order(db(), order_sn, reason=reason)
    db().commit()
    return jsonify(_view(order.model))
