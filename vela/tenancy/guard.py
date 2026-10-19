"""高危操作的租户防护。

export/delete 类操作一旦串了租户就是事故,宁可在这里多拦一道。
"""

from __future__ import annotations

from vela.config.errors import TenantError
from vela.config.logging import get_logger

log = get_logger(__name__)


def require_explicit_tenant(provided: str | None, *, action: str) -> str:
    """导出/删除类接口的租户参数必须调用方显式给,不兜底 current_tenant。"""
    if not provided:
        raise TenantError(
            f"{action} 属于 export/delete 类操作必须显式指定租户,不接受隐式上下文"
        )
    return provided


def audit_cross_tenant_access(source_tenant: str, target_tenant: str, action: str) -> bool:
    """跨租户访问:打告警日志并返回 True;同租户返回 False,不打日志。

    返回值给调用方决定放行还是拒,这里只负责留痕。
    """
    if source_tenant != target_tenant:
        log.warning(
            "cross_tenant_access",
            source_tenant=source_tenant,
            target_tenant=target_tenant,
            action=action,
        )
        return True
    return False
