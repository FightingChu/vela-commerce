"""trace/租户头模型。给网关侧对账脚本和单测复用,alias 是带横线的头名。"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from vela.config.constants import TENANT_HEADER, TRACE_HEADER


class TraceHeaders(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    trace_id: str = Field(alias=TRACE_HEADER)
    tenant_id: str | None = Field(default=None, alias=TENANT_HEADER)
