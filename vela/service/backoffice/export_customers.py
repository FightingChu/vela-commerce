"""客户导出。和 export_orders 同款规矩:显式租户 + batch_iter。

手机号库里就是脱敏串,直接出;收货地址表不导(含明文收件人电话,
整改随 #VT-2103,在那之前导出范围收窄到档案本身)。
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from vela.config.errors import ValidationError
from vela.db import batch_iter
from vela.domain.customer.models import CustomerModel
from vela.service import audit_bridge, tenant_guard
from vela.service.backoffice.csv_sink import DEFAULT_BATCH_ROWS, CsvSink
from vela.service.converters import dt_to_iso

HEADERS = [
    "customer_id",
    "external_id",
    "nickname",
    "phone",
    "tier",
    "registered_at",
]


def _row(model: CustomerModel) -> dict:
    return {
        "customer_id": model.id,
        "external_id": model.external_id,
        "nickname": model.nickname,
        "phone": model.phone or "",
        "tier": model.tier,
        "registered_at": dt_to_iso(model.registered_at) or "",
    }


def export_customers(
    session: Session,
    tenant: str,
    *,
    path: str | None = None,
    sink: CsvSink | None = None,
    batch_rows: int = DEFAULT_BATCH_ROWS,
    operator: str | None = None,
) -> dict:
    """导出客户档案(软删的不出)。返回 {"rows","tenant","path"}。"""
    with tenant_guard.explicit_tenant(tenant, action="export_customers"):
        if sink is None and not path:
            raise ValidationError("export_customers 需要 path 或 sink 之一")

        stmt = select(CustomerModel).where(CustomerModel.deleted_at.is_(None))
        owned: CsvSink | None = None
        target = sink
        try:
            if target is None:
                target = owned = CsvSink(path, headers=HEADERS)
            count = 0
            for model in batch_iter(
                session, stmt, batch_rows=batch_rows, pk_attr=CustomerModel.id
            ):
                target.write_row(_row(model))
                count += 1
        finally:
            if owned is not None:
                owned.close()

        audit_bridge.record_admin_action(
            session,
            action="export.customers",
            target_type="customer",
            target_id=tenant,
            detail={"rows": count, "path": path, "operator": operator},
        )
        return {"rows": count, "tenant": tenant, "path": path}
