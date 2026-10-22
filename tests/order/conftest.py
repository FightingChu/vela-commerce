"""order 域测试本地 fixture。

根 conftest 的 `_clean_caches` 里 `import vela.config.flags as flags_mod`
拿到的是 flags 函数而不是模块——vela/config/__init__.py 把 flags 函数
re-export 出来,顶掉了子模块属性。根因在 vela/config/__init__.py
(应该只 re-export Flags 类或者改名,见 #VT-2199),那边不归本域管,
先用同名 fixture 盖掉,等修了再删这里。
"""

from __future__ import annotations

import pytest

import vela.db.tenant as tenant_mod
from vela.config.flags import reset_flags
from vela.config.settings import reset_settings


@pytest.fixture(autouse=True)
def _clean_caches():
    reset_settings()
    reset_flags()
    yield
    reset_settings()
    reset_flags()


@pytest.fixture(autouse=True)
def _clean_tenant():
    tenant_mod._local.__dict__.pop("tenant", None)
    yield
    tenant_mod._local.__dict__.pop("tenant", None)
