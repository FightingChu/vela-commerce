"""租户注册表。

注册表本身是全局的,不带 tenant_id 列——给租户做隔离的表
反而不能被租户过滤,不然 bootstrap 阶段谁都查不到它。
"""

from __future__ import annotations

import enum

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from vela.db import Base, PkMixin, TimestampMixin


class Plan(str, enum.Enum):
    FREE = "FREE"
    PRO = "PRO"
    ENTERPRISE = "ENTERPRISE"


class TenantRegistryModel(Base, PkMixin, TimestampMixin):
    # 基类的自动表名会生成 "tenant_registrys",别扭,显式指定
    __tablename__ = "tenant_registry"

    tenant_id: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    # 存枚举 value 而不是 sqlalchemy Enum 类型,pg 上改枚举成员不用动 DDL
    plan: Mapped[str] = mapped_column(String(16), default=Plan.FREE.value, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # 分片路由提示,shard_router 读;空表示走默认路由
    shard_hint: Mapped[str | None] = mapped_column(String(64))

    def __repr__(self) -> str:  # pragma: no cover - 排查日志用
        return f"<TenantRegistry {self.tenant_id} plan={self.plan}>"
