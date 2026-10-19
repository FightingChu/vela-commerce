"""builder 公共查询小件。

报表直查模型不走 Repository,租户/软删过滤得自己套——忘了套
就是把全租户数据导给一个商户,这种事故一次都不许有,所以统一
从 scoped_select 进,别在 builder 里裸 select()。
"""

from __future__ import annotations

from sqlalchemy import Select, select

from vela.db import SoftDeleteMixin, TenantColumnMixin, current_tenant


def scoped_select(model) -> Select:
    """等价于 Repository._scoped,给不走 Repository 的只读查询用。"""
    stmt = select(model)
    if issubclass(model, TenantColumnMixin):
        stmt = stmt.where(model.tenant_id == current_tenant())
    if issubclass(model, SoftDeleteMixin):
        stmt = stmt.where(model.deleted_at.is_(None))
    return stmt
