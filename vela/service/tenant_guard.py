"""租户防护的 service 侧封装。

export/delete 类操作的显式租户要求从 tenancy.guard 借来,包成
contextmanager,让 backoffice 的导出入口写起来少一层缩进。
普通读写不经过这里,走 db 层的隐式 current_tenant 就行。
"""

from __future__ import annotations

import contextlib
from collections.abc import Iterator

from vela.db import DEFAULT_TENANT, current_tenant, tenant_context
from vela.tenancy.guard import audit_cross_tenant_access, require_explicit_tenant


@contextlib.contextmanager
def explicit_tenant(tenant: str | None, *, action: str) -> Iterator[str]:
    """高危操作的租户入口:必须显式给,校验通过后绑进上下文。

    with explicit_tenant(tenant, action="export_orders") as t: ...
    """
    resolved = require_explicit_tenant(tenant, action=action)
    with tenant_context(resolved):
        yield resolved


@contextlib.contextmanager
def tenant_or_default(tenant: str | None) -> Iterator[str]:
    """普通操作:给了就切,没给沿用隐式上下文(兜底 DEFAULT_TENANT)。"""
    if tenant:
        with tenant_context(tenant):
            yield tenant
    else:
        yield current_tenant()


def cross_tenant_allowed(source: str | None, target: str, action: str) -> bool:
    """跨租户放行前留痕。source 为空按 DEFAULT_TENANT 比。"""
    return not audit_cross_tenant_access(source or DEFAULT_TENANT, target, action)
