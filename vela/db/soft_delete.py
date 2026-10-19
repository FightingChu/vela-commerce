"""软删除。现状:deleted_at 时间戳,空 = 未删。

历史包袱:早期几批表没有这列,后来补迁移逐个加的,所以不是每张表都有。
带 SoftDeleteMixin 的表查询必须走 not_deleted(),裸 select 出来删过的行
出过线上事故(#VT-1987),别再犯。
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy import DateTime
from sqlalchemy.orm import Mapped, mapped_column

from vela.config.clocks import utc_now


class SoftDeleteMixin:
    deleted_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), default=None, nullable=True, index=True
    )

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None

    def soft_delete(self) -> None:
        if self.deleted_at is None:
            self.deleted_at = utc_now()

    def restore(self) -> None:
        """只允许审计流程调用,业务侧恢复走 auditing 包。"""
        self.deleted_at = None
