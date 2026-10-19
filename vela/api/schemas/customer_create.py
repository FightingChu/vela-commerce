"""客户注册入参。phone 明文进来,service 层负责脱敏,DTO 不碰。"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class CustomerCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    external_id: str = Field(min_length=1, max_length=64)
    nickname: str = Field(min_length=1, max_length=128)
    phone: str | None = Field(default=None, max_length=32)
    tier: str = "V0"
