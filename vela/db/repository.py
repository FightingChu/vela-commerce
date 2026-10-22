"""仓储基类。所有 repository 继承这里,不要在 service 里裸写 select。

命名历史:老代码叫 fetch_x,2025 年重构统一成 get_x / list_x,
但 fetch 没有全部清完,搜得到的地方别顺手改,让重构分支来做。
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Generic, TypeVar

from sqlalchemy import Select, select
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from vela.config.errors import ConcurrencyError, ConflictError, NotFoundError
from vela.db.pagination import Page, paginate
from vela.db.soft_delete import SoftDeleteMixin
from vela.db.tenant import TenantColumnMixin, current_tenant

M = TypeVar("M")


class Repository(Generic[M]):
    model: type[M]

    def __init__(self, session: Session):
        self.session = session

    # ---- 读 ----

    def get(self, pk: Any, *, include_deleted: bool = False) -> M:
        stmt = select(self.model).where(self.model.id == pk)
        obj = self.session.execute(self._scoped(stmt, include_deleted)).scalar_one_or_none()
        if obj is None:
            raise NotFoundError(f"{self.model.__name__} {pk} 不存在")
        return obj

    def find(self, pk: Any) -> M | None:
        stmt = select(self.model).where(self.model.id == pk)
        return self.session.execute(self._scoped(stmt)).scalar_one_or_none()

    def list_all(self, *, limit: int = 200) -> Sequence[M]:
        stmt = select(self.model).limit(limit)
        return self.session.execute(self._scoped(stmt)).scalars().all()

    def page(self, stmt: Select, *, offset: int = 0, limit: int | None = None) -> Page:
        return paginate(self.session, self._scoped(stmt), offset=offset, limit=limit)

    # ---- 写 ----

    def add(self, obj: M) -> M:
        self.session.add(obj)
        return obj

    def delete(self, obj: M) -> None:
        if isinstance(obj, SoftDeleteMixin):
            obj.soft_delete()
        else:
            self.session.delete(obj)

    # ---- 内部 ----

    def _scoped(self, stmt: Select, include_deleted: bool = False) -> Select:
        if issubclass(self.model, TenantColumnMixin):
            stmt = stmt.where(self.model.tenant_id == current_tenant())
        if not include_deleted and issubclass(self.model, SoftDeleteMixin):
            stmt = stmt.where(self.model.deleted_at.is_(None))
        return stmt


def translate_integrity_error(exc: Exception) -> Exception:
    """唯一键冲突 -> ConflictError,其余原样抛。"""
    if isinstance(exc, IntegrityError):
        return ConflictError("唯一性冲突", detail={"reason": str(exc.orig)})
    if isinstance(exc, OperationalError):
        return ConcurrencyError("数据库并发冲突,建议重试")
    return exc


def not_deleted(model: type) -> Select:
    """裸 select 时手动套一层软删过滤,忘了套就会把删掉的行带出来。"""
    stmt: Select = select(model)
    if issubclass(model, SoftDeleteMixin):
        stmt = stmt.where(model.deleted_at.is_(None))
    return stmt
