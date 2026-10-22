"""共享 fixtures。

db_session:内存 sqlite,建全表。各域模型在自己包的 models.py 里
import 时注册到 Base.metadata,所以测试文件要先 import 对应模型模块
(直接 import 域包 __init__ 即可)。
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

import vela.config.settings as settings_mod

# 注意:不能写 `import vela.config.flags as flags_mod`——
# vela/config/__init__.py 里 re-export 了同名函数 flags,会把模块属性盖掉,
# import-as 拿到的是函数不是模块。用 from-import 才拿得到真身。
from vela.config.flags import reset_flags
from vela.db import tenant as tenant_mod
from vela.db.base import Base


@pytest.fixture(autouse=True)
def _clean_caches():
    """每个测试都拿到干净的 settings/flags/租户上下文。"""
    settings_mod.reset_settings()
    reset_flags()
    yield
    settings_mod.reset_settings()
    reset_flags()


@pytest.fixture(autouse=True)
def _clean_tenant():
    tenant_mod._local.__dict__.pop("tenant", None)
    yield
    tenant_mod._local.__dict__.pop("tenant", None)


@pytest.fixture
def db_session():
    engine = create_engine("sqlite://", future=True, echo=False)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, future=True, expire_on_commit=False)
    session: Session = factory()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture
def frozen_clock():
    from vela.config.clocks import FrozenClock

    return FrozenClock()
