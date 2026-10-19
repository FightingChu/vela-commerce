"""SKU 档案入参。"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class SkuCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sku_code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=255)
    category: str | None = Field(default=None, max_length=64)
    unit: str = "件"
    weight_grams: int | None = Field(default=None, gt=0)
    is_active: bool = True
    specs: dict | None = None
