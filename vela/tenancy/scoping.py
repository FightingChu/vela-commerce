"""查询的租户过滤与对象归属校验。

Repository._scoped 已覆盖走仓储基类的路径,这里给裸 select、
跨域联查用。忘了套就是数据泄露,code review 里见过三次了。
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import Select

from vela.config.errors import TenantError
from vela.db.tenant import current_tenant


def apply_tenant_filter(stmt: Select, model: type) -> Select:
    """模型带 tenant_id 列就自动补 where,没有的(全局表)原样返回。"""
    if "tenant_id" in model.__table__.columns:
        stmt = stmt.where(model.tenant_id == current_tenant())
    return stmt


def ensure_same_tenant(a: Any, b: Any) -> None:
    """跨对象操作(合并/拆单/转移)前校验同租户,不一致直接拒。"""
    ta = getattr(a, "tenant_id", None)
    tb = getattr(b, "tenant_id", None)
    if ta != tb:
        raise TenantError("跨租户操作被拒绝", detail={"tenant_a": ta, "tenant_b": tb})
