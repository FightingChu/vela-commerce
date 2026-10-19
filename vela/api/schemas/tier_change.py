"""客户等级变更入参。降级会被 service 层拦,DTO 只管形状。"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class TierChange(BaseModel):
    model_config = ConfigDict(extra="forbid")

    customer_id: int = Field(gt=0)
    tier: str = Field(min_length=1, max_length=16)
