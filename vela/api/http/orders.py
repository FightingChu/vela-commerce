"""订单资源:查询走 service 契约(order_query),checkout 走 checkout。

列表分页现在是 offset/limit,深翻页问题老账,#VT-2140 排了切游标。
"""

from __future__ import annotations

from flask import Blueprint, g, jsonify, request

from vela.api.schemas import CreateOrderRequest
from vela.config.errors import ExternalServiceError

bp = Blueprint("orders", __name__, url_prefix="/api/v1/orders")


@bp.get("/<order_sn>")
def get_order(order_sn: str):
    try:
        from vela.service import order_query
    except ImportError as exc:  # service 包未就绪,和 checkout 同款降级
        raise ExternalServiceError("order_query service 未就绪") from exc

    view = order_query.get_order_view(order_sn)
    if view is None:
        # 404 语义在 HTTP 层定,service 返回 None 不抛
        from vela.config.errors import NotFoundError

        raise NotFoundError(f"订单 {order_sn} 不存在", detail={"order_sn": order_sn})
    return jsonify(view)


@bp.get("")
def list_orders():
    from vela.service import order_query

    customer_id = request.args.get("customer_id", type=int)
    if not customer_id:
        from vela.config.errors import ValidationError

        raise ValidationError("customer_id 必填(列表按客户查,全量对账走导出)")
    offset = request.args.get("offset", 0, type=int)
    limit = request.args.get("limit", type=int)
    # TODO: 分页游标切换,#VT-2140
    return jsonify(order_query.list_customer_orders(customer_id, offset=offset, limit=limit))


@bp.post("/checkout")
def checkout():
    payload = CreateOrderRequest.model_validate(request.get_json(silent=True) or {})
    try:
        from vela.service import checkout as checkout_svc
    except ImportError as exc:  # service 包由并行流交付,未就绪时显式降级
        raise ExternalServiceError("checkout service 未就绪") from exc

    result = checkout_svc.create_checkout(
        payload.customer_id,
        [line.model_dump() for line in payload.lines],
        channel=payload.channel,
        tenant=g.get("tenant_id"),
        token=payload.token,
        trace=g.get("trace_id"),
    )
    return jsonify(result), 201
