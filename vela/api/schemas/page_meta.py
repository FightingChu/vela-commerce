"""分页元信息。列表接口统一把 Page 摊平成这个形状。"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class PageMeta(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total: int = Field(ge=0)
    offset: int = Field(ge=0)
    limit: int = Field(gt=0)

    @property
    def has_next(self) -> bool:
        return self.offset + self.limit < self.total
