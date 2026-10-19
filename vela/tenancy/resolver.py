"""租户解析:请求头 / 域名 -> 租户标识。

规则别放宽:租户 id 会拼进缓存键和表名分片,放个奇怪的字符
进来,炸的是下游(#VT-601 事故,underscore 租户打穿了 Redis 键空间)。
"""

from __future__ import annotations

import re

from vela.config.constants import TENANT_HEADER
from vela.config.errors import TenantError

DEFAULT_TENANT = "main"

# 小写字母/数字开头,允许中划线,总长 1-32
_TENANT_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,31}$")


def _validate(tid: str) -> str:
    if not tid or len(tid) > 32 or not _TENANT_RE.match(tid):
        raise TenantError(f"非法租户标识: {tid!r}")
    return tid


def resolve(headers: dict) -> str:
    """从请求头解析租户,缺省 main;非法字符直接抛 TenantError。"""
    tid = (headers.get(TENANT_HEADER) or DEFAULT_TENANT).strip().lower()
    return _validate(tid)


def resolve_from_host(host: str) -> str:
    """内网子域名首段当租户:acme.api.vela.internal -> acme。

    host 形如 acme.vela.internal(两段)没有独立子域,回落 main。
    """
    if not host:
        return DEFAULT_TENANT
    host = host.strip().lower().split(":")[0]  # 去端口
    labels = host.split(".")
    if len(labels) < 3:
        return DEFAULT_TENANT
    first = labels[0]
    if first in ("www", "api", "admin", "ops"):
        # 平台自身的域名不算租户
        return DEFAULT_TENANT
    return _validate(first)
