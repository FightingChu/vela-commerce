"""多租户包。

db 层的隐式租户(vela.db.tenant)只管"当前是哪个租户";
这里管"租户从哪来、怎么校验、缓存键和查询怎么带上它"。
"""

from vela.tenancy.guard import audit_cross_tenant_access, require_explicit_tenant
from vela.tenancy.keys import cache_key, scoped
from vela.tenancy.models import TenantRegistryModel
from vela.tenancy.registry import TenantRegistry
from vela.tenancy.resolver import resolve, resolve_from_host
from vela.tenancy.scoping import apply_tenant_filter, ensure_same_tenant

__all__ = [
    "TenantRegistry",
    "TenantRegistryModel",
    "apply_tenant_filter",
    "audit_cross_tenant_access",
    "cache_key",
    "ensure_same_tenant",
    "require_explicit_tenant",
    "resolve",
    "resolve_from_host",
    "scoped",
]
