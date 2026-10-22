"""多租户在 db 层的钩子。

现状是"隐式":模型带 tenant_id 列,中间件把租户塞进线程局部,
查询基类自动过滤。显式化过渡方案见 ADR-0006(apply_tenant_filter)。
"""

from __future__ import annotations

import contextlib
import threading
from collections.abc import Iterator

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from vela.config.errors import TenantError

_local = threading.local()

DEFAULT_TENANT = "main"


class TenantColumnMixin:
    tenant_id: Mapped[str] = mapped_column(
        String(32), nullable=False, default=DEFAULT_TENANT, index=True
    )


def current_tenant() -> str:
    return getattr(_local, "tenant", DEFAULT_TENANT)


@contextlib.contextmanager
def tenant_context(tenant_id: str) -> Iterator[None]:
    if not tenant_id or len(tenant_id) > 32:
        raise TenantError(f"非法租户标识: {tenant_id!r}")
    prev = getattr(_local, "tenant", None)
    _local.tenant = tenant_id
    try:
        yield
    finally:
        if prev is None:
            if hasattr(_local, "tenant"):
                del _local.tenant
        else:
            _local.tenant = prev


def require_tenant(explicit: str | None = None) -> str:
    """导出/审计等高危操作要求显式给租户,不给就用当前上下文的,再没有就报错。"""
    tid = explicit or current_tenant()
    if not tid:
        raise TenantError("缺少租户上下文")
    return tid
