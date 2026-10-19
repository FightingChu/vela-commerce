"""分页。现状是 offset/limit,深翻页性能问题见 README 已知问题第 2 条。

报表导出侧的 batch_iter() 是 2026-04 加的,API 侧还没切。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from vela.config.settings import get_settings


@dataclass
class Page:
    items: Sequence[Any]
    total: int
    offset: int
    limit: int

    @property
    def has_next(self) -> bool:
        return self.offset + len(self.items) < self.total

    def as_dict(self, *, item_key: str = "items") -> dict:
        return {
            item_key: list(self.items),
            "total": self.total,
            "offset": self.offset,
            "limit": self.limit,
        }


def paginate(
    session: Session,
    stmt: Select,
    *,
    offset: int = 0,
    limit: int | None = None,
    count_key: str | None = None,
) -> Page:
    """标准 offset 分页。limit 不传走 settings.default_page_size。"""
    if offset < 0:
        raise ValueError(f"offset 不能为负: {offset}")
    s = get_settings()
    limit = limit if limit is not None else s.default_page_size
    if limit <= 0:
        raise ValueError(f"limit 必须为正: {limit}")
    if limit > s.max_page_size:
        limit = s.max_page_size

    total = session.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    rows = session.execute(stmt.offset(offset).limit(limit)).scalars().all()
    return Page(items=rows, total=total, offset=offset, limit=limit)


def batch_iter(
    session: Session,
    stmt: Select,
    *,
    batch_rows: int | None = None,
    pk_attr: Any = None,
):
    """按主键递增分批,给导出和大对账用,避开 offset 深翻页。

    注意:遍历期间别往同一 session 写,游标会漂。
    """
    from vela.config.settings import get_settings as _gs

    batch_rows = batch_rows or _gs().reconcile_batch_rows
    if pk_attr is None:
        pk_attr = stmt.columns[0]
    last_pk = None
    while True:
        s = stmt
        if last_pk is not None:
            s = stmt.where(pk_attr > last_pk)
        rows = session.execute(s.order_by(pk_attr).limit(batch_rows)).scalars().all()
        if not rows:
            return
        for row in rows:
            yield row
        last_pk = rows[-1].id if hasattr(rows[-1], "id") else rows[-1][0]
