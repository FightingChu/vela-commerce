"""Engine 工厂。测试环境用 sqlite,分片逻辑见 shard_router。"""

from __future__ import annotations

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine

from vela.config.settings import get_settings

_ENGINES: dict[str, Engine] = {}


def build_engine(url: str, *, pool_size: int | None = None, echo: bool = False) -> Engine:
    kwargs: dict = {"echo": echo, "future": True}
    if url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
    else:
        s = get_settings()
        kwargs.update(
            pool_size=pool_size or s.db_pool_size,
            pool_recycle=s.db_pool_recycle,
            pool_pre_ping=True,
        )
    engine = create_engine(url, **kwargs)
    if url.startswith("sqlite"):
        _enable_sqlite_fk(engine)
    return engine


def _enable_sqlite_fk(engine: Engine) -> None:
    @event.listens_for(engine, "connect")
    def _set_fk(dbapi_conn, _record):  # pragma: no cover - sqlite only
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


def primary_engine() -> Engine:
    url = get_settings().db_url
    if url not in _ENGINES:
        _ENGINES[url] = build_engine(url)
    return _ENGINES[url]


def replica_engine() -> Engine:
    url = get_settings().effective_replica_url
    if url not in _ENGINES:
        _ENGINES[url] = build_engine(url)
    return _ENGINES[url]


def reset_engines() -> None:
    """测试之间清理连接池。"""
    global _ENGINES
    _ENGINES = {}
