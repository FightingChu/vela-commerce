"""订单行。行没有独立 service,直接读 OrderRepository.load_lines。"""

from __future__ import annotations

from flask import Blueprint, jsonify

from vela.api.middleware import db
from vela.config.errors import NotFoundError
from vela.domain.order.models import OrderLineModel
from vela.domain.order.repository import OrderRepository

bp = Blueprint("order_lines", __name__, url_prefix="/api/v1/order-lines")


def _view(line: OrderLineModel) -> dict:
    return {
        "id": line.id,
        "order_id": line.order_id,
        "sku_id": line.sku_id,
        "qty": line.qty,
        "unit_price": str(line.unit_price),
        "line_amount": str(line.line_amount),
        "discount_share": str(line.discount_share),
        "line_status": line.line_status,
    }


@bp.get("/by-order/<order_sn>")
def list_by_order(order_sn: str):
    # 行挂在订单下,先定位订单(带租户过滤),再拉行
    order = OrderRepository(db()).get_by_sn(order_sn)
    lines = OrderRepository(db()).load_lines(order.id)
    return jsonify({"order_sn": order_sn, "items": [_view(l) for l in lines]})


@bp.get("/<int:line_id>")
def get_line(line_id: int):
    from sqlalchemy import select

    line = db().execute(
        select(OrderLineModel).where(OrderLineModel.id == line_id)
    ).scalar_one_or_none()
    if line is None:
        raise NotFoundError(f"订单行 {line_id} 不存在", detail={"line_id": line_id})
    return jsonify(_view(line))
