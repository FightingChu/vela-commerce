"""订单查询。api 并行任务的契约模块,签名一字不动。

读侧走 _scope(默认 session_scope,实际全是大水印只读 SQL,以后切
replica_scope 的话只改这里);查不到返回 None 不抛——视图接口对
"没这条数据"不是错误,调用方自己决定 404 还是空态。
"""

from __future__ import annotations

from sqlalchemy import select

from vela.db import paginate, session_scope
from vela.domain.order import OrderNotFoundError, OrderRepository
from vela.domain.order.models import OrderModel
from vela.service.converters import order_to_view

_scope = session_scope


def get_order_view(order_sn: str) -> dict | None:
    """单订单视图。软删单当不存在,和 get_by_sn 的口径一致。"""
    with _scope() as session:
        try:
            model = OrderRepository(session).get_by_sn(order_sn)
        except OrderNotFoundError:
            return None
        lines = OrderRepository(session).load_lines(model.id)
        return order_to_view(model, lines)


def list_customer_orders(
    customer_id: int,
    *,
    offset: int = 0,
    limit: int | None = None,
) -> dict:
    """客户订单分页,id 倒序(最新在前)。返回 {"items","total","offset","limit"}。

    裸 select 的软删过滤要手动套——忘了套就会把用户删掉的历史单
    带出来,db/repository.py 头注释里强调过。
    """
    with _scope() as session:
        stmt = (
            select(OrderModel)
            .where(
                OrderModel.customer_id == customer_id,
                OrderModel.deleted_at.is_(None),
            )
            .order_by(OrderModel.id.desc())
        )
        page = paginate(session, stmt, offset=offset, limit=limit)
        repo = OrderRepository(session)
        items = [order_to_view(model, repo.load_lines(model.id)) for model in page.items]
        return {
            "items": items,
            "total": page.total,
            "offset": page.offset,
            "limit": page.limit,
        }
