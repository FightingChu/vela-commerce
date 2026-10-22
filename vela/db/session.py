"""Session 管理:工作单元模式,一个请求一个 session。

Flask 侧在 vela/api/http/middleware.py 里挂了 teardown;job 侧自己
with session_scope()。
"""

from __future__ import annotations

import contextlib
from collections.abc import Iterator

from sqlalchemy.orm import Session, sessionmaker

from vela.db.engine import primary_engine, replica_engine

_SessionFactory = sessionmaker(bind=None, future=True, expire_on_commit=False)
_ReplicaFactory = sessionmaker(bind=None, future=True, expire_on_commit=False)

_BOUND = False


def _ensure_bound() -> None:
    global _BOUND
    if not _BOUND:
        _SessionFactory.configure(bind=primary_engine())
        _ReplicaFactory.configure(bind=replica_engine())
        _BOUND = True


@contextlib.contextmanager
def session_scope() -> Iterator[Session]:
    """写操作用。异常自动 rollback,正常 commit。"""
    _ensure_bound()
    session = _SessionFactory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def replica_scope() -> contextlib.AbstractContextManager[Session]:
    """只读查询优先走这里,主库压力大。没配副本时等价于主库。"""
    _ensure_bound()
    return _replica_scope_impl()


@contextlib.contextmanager
def _replica_scope_impl():
    session = _ReplicaFactory()
    try:
        yield session
    finally:
        session.close()


def current_session() -> Session:
    """裸拿一个 session,自己管生命周期。老代码大量这么用,新的别学。"""
    _ensure_bound()
    return _SessionFactory()


def reset_session_factories() -> None:
    global _BOUND
    _BOUND = False
