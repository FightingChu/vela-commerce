"""pricing 测试局部覆盖。

上层 tests/conftest.py 的 _clean_caches 里 `import vela.config.flags as
flags_mod` 实际拿到的是 vela.config.__init__ re-export 的 flags() 函数
(同名遮蔽),reset_flags 调不起来;这里用 sys.modules 直取模块重写该
fixture,不动共享 conftest。
"""

from __future__ import annotations

import sys

import pytest

import vela.config.settings as settings_mod

_flags_mod = sys.modules["vela.config.flags"]


@pytest.fixture(autouse=True)
def _clean_caches():
    settings_mod.reset_settings()
    _flags_mod.reset_flags()
    yield
    settings_mod.reset_settings()
    _flags_mod.reset_flags()
