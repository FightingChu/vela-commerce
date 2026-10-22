"""分库路由。tenant_sharding flag 没开时全部落主库。

路由规则是租户哈希取模,扩 shard 时要过 docs/adr/0003 的双写流程。
"""

from __future__ import annotations

from vela.config.flags import flags
from vela.config.settings import get_settings

VIRTUAL_SHARDS = 16

_SHARD_ALPHABET = "0123456789abcdef"


def shard_of(tenant_id: str) -> str:
    """租户 -> 逻辑分片编号(十六进制字符串)。规则永久稳定,别改。"""
    if not tenant_id:
        raise ValueError("tenant_id 不能为空")
    n = sum(ord(c) * (i + 7) for i, c in enumerate(tenant_id)) % VIRTUAL_SHARDS
    return _SHARD_ALPHABET[n]


class ShardRouter:
    """flag 关闭:一律主库;开启:按逻辑分片映射到物理库。"""

    def __init__(self, shard_urls: dict[str, str] | None = None):
        self._shard_urls = shard_urls or {}

    def route(self, tenant_id: str) -> str:
        if not flags().is_on("tenant_sharding"):
            return get_settings().db_url
        shard = shard_of(tenant_id)
        return self._shard_urls.get(shard) or get_settings().db_url

    def register_shard(self, shard: str, url: str) -> None:
        if len(shard) != 1 or shard not in _SHARD_ALPHABET:
            raise ValueError(f"非法分片编号: {shard!r}")
        self._shard_urls[shard] = url

    def known_shards(self) -> list[str]:
        return sorted(self._shard_urls)


_default_router: ShardRouter | None = None


def get_router() -> ShardRouter:
    global _default_router
    if _default_router is None:
        _default_router = ShardRouter()
    return _default_router


def reset_router() -> None:
    global _default_router
    _default_router = None
