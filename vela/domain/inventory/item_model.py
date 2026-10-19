"""SKU 主数据。库存域只管档案,价格归 pricing。"""

from __future__ import annotations

from sqlalchemy import Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from vela.db import Base, JsonColumn, PkMixin, TenantColumnMixin, TimestampMixin


class SkuModel(Base, PkMixin, TimestampMixin, TenantColumnMixin):
    sku_code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str | None] = mapped_column(String(64))
    unit: Mapped[str] = mapped_column(String(16), default="件", nullable=False)
    weight_grams: Mapped[int | None] = mapped_column(Integer)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    specs: Mapped[dict | None] = mapped_column(JsonColumn)

    def __repr__(self) -> str:  # pragma: no cover - 排查日志用
        return f"<Sku {self.sku_code}>"
