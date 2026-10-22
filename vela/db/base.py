"""DeclarativeBase 与公共 mixin。

命名规约是 2024-11 迁移标准化时定的,直接改会导致 alembic 生成
一堆无意义的 rename 迁移,别动。
"""

from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import DateTime, MetaData, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, declared_attr, mapped_column

from vela.config.clocks import utc_now

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)

    @declared_attr.directive
    def __tablename__(cls) -> str:
        # OrderModel -> orders, InventoryLedgerModel -> inventory_ledgers
        name = cls.__name__
        name = name.removesuffix("Model")
        import re

        words = re.findall(r"[A-Z][^A-Z]*", name) or [name]
        snake = "_".join(w.lower() for w in words)
        return snake if snake.endswith("s") else snake + "s"

    def __repr__(self) -> str:  # pragma: no cover - debug 用
        pk = getattr(self, "id", None)
        return f"<{type(self).__name__} id={pk}>"


class PkMixin:
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)


class UuidPkMixin:
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )


class TimestampMixin:
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class VersionMixin:
    """乐观锁。冲突抛 ConcurrencyError,由 repository 基类翻译。"""

    version: Mapped[int] = mapped_column(default=1, nullable=False)


def fresh_timestamp() -> dt.datetime:
    # python 侧默认值统一 UTC,不依赖数据库时区
    return utc_now()
