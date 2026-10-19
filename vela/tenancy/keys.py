"""缓存键统一入口。

租户前缀必须过这里拼,业务代码里别手写 f"t:{tid}:..."——
漏一段前缀就是跨租户串缓存,#VT-601 之后定的规矩。
"""

from __future__ import annotations

from vela.db.tenant import current_tenant


def cache_key(*parts: str, tenant: str | None = None) -> str:
    """拼带租户前缀的缓存键;tenant 缺省取当前上下文。"""
    if not parts:
        raise ValueError("cache_key 至少要一个 part")
    tid = tenant if tenant is not None else current_tenant()
    return f"t:{tid}:{':'.join(parts)}"


# 已经带 t: 前缀的键原样放行,否则补当前租户前缀
def scoped(key: str) -> str:
    if key.startswith("t:"):
        return key
    return cache_key(key)
