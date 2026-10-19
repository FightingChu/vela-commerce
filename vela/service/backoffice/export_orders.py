"""订单导出。backoffice 高危操作:必须显式给租户,不走隐式上下文。

分批用 batch_iter(主键游标,避开 offset 深翻页);遍历期间只读,
别往同一 session 写——游标会漂,pagination.py 里警告过。
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from vela.db import batch_iter
from vela.domain.order.models import OrderModel
from vela.service import audit_bridge, tenant_guard
from vela.service.backoffice.csv_sink import DEFAULT_BATCH_ROWS, CsvSink

HEADERS = [
    "order_sn",
    "customer_id",
    "status",
    "channel",
    "total",
    "discount",
    "paid",
    "created_at",
]


def _row(model) -> dict:
    from vela.service.converters import dt_to_iso, money

    return {
        "order_sn": model.order_sn,
        "customer_id": model.customer_id,
        "status": model.status,
        "channel": model.channel,
        "total": money(model.total_amount),
        "discount": money(model.discount_amount),
        "paid": money(model.paid_amount),
        "created_at": dt_to_iso(model.created_at) or "",
    }


def export_orders(
    session: Session,
    tenant: str,
    *,
    path: str | None = None,
    sink: CsvSink | None = None,
    batch_rows: int = DEFAULT_BATCH_ROWS,
    operator: str | None = None,
) -> dict:
    """导出订单到 CSV。path 与 sink 二选一(都给以 sink 为准)。

    返回 {"rows","tenant","path"}。sink 由调用方传入时不负责 close。
    """
    with tenant_guard.explicit_tenant(tenant, action="export_orders"):
        if sink is None and not path:
            from vela.config.errors import ValidationError

            raise ValidationError("export_orders 需要 path 或 sink 之一")

        stmt = select(OrderModel).where(OrderModel.deleted_at.is_(None))
        owned: CsvSink | None = None
        target = sink
        try:
            if target is None:
                target = owned = CsvSink(path, headers=HEADERS)
            count = 0
            # batch_iter 默认取 stmt 第一列当游标,这里显式给 id,稳
            for model in batch_iter(
                session, stmt, batch_rows=batch_rows, pk_attr=OrderModel.id
            ):
                target.write_row(_row(model))
                count += 1
        finally:
            if owned is not None:
                owned.close()

        audit_bridge.record_admin_action(
            session,
            action="export.orders",
            target_type="order",
            target_id=tenant,
            detail={"rows": count, "path": path, "operator": operator},
        )
        return {"rows": count, "tenant": tenant, "path": path}
