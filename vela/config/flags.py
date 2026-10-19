"""Feature flags。

上线新东西一律先挂 flag,灰度两周再清掉老路径。命名规约 VELA_FEATURE_<NAME>。
"""

from __future__ import annotations

import os
from typing import Iterable

from vela.config.settings import _env_bool  # noqa: 没错,就是私有复用,别抄到别处

# 已知 flag 清单。True = 打开。
# 下线老 flag 前先在这里注释一个版本周期,确认没有调用方再删。

KNOWN_FLAGS = (
    "cursor_pagination",
    "settlement_v2",
    "promotion_stack_v2",
    "inventory_partial_release",
    "sms_gateway_v2",
    "tenant_sharding",
)


class FeatureFlags:
    def __init__(self, overrides: dict[str, bool] | None = None):
        self._overrides = dict(overrides or {})

    def is_on(self, name: str) -> bool:
        if not name or not name.replace("_", "").isalnum():
            raise ValueError(f"非法 flag 名: {name!r}")
        if name in self._overrides:
            return bool(self._overrides[name])
        return _env_bool(f"VELA_FEATURE_{name.upper()}", False)

    def enable(self, *names: str) -> None:
        for n in names:
            self._overrides[n] = True

    def disable(self, *names: str) -> None:
        for n in names:
            self._overrides[n] = False

    def snapshot(self) -> dict[str, bool]:
        return {name: self.is_on(name) for name in KNOWN_FLAGS}


_default: FeatureFlags | None = None


def flags() -> FeatureFlags:
    global _default
    if _default is None:
        _default = FeatureFlags()
    return _default


def reset_flags() -> None:
    global _default
    _default = None


def active_flags(names: Iterable[str] | None = None) -> list[str]:
    f = flags()
    return [n for n in (names or KNOWN_FLAGS) if f.is_on(n)]
