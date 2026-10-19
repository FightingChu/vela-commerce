"""租户注册入参。tenant_id 上限 32 和 db 层 tenant_context 对齐。"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class TenantIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tenant_id: str = Field(min_length=1, max_length=32)
    name: str = Field(min_length=1, max_length=128)
    plan: Literal["FREE", "PRO", "ENTERPRISE"] = "FREE"
    shard_hint: str | None = Field(default=None, max_length=64)
