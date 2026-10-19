"""收货地址入参。"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class AddressIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    receiver: str = Field(min_length=1, max_length=64)
    phone: str = Field(min_length=1, max_length=32)
    province: str = Field(min_length=1, max_length=32)
    city: str = Field(min_length=1, max_length=32)
    district: str | None = Field(default=None, max_length=32)
    detail: str = Field(min_length=1, max_length=255)
    is_default: bool = False
