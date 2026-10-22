"""对账:库存快照 vs 快照,给出差异行。

凌晨 job 跑:先 take_snapshot,和上一轮(或盘点导入的期望值)
diff,差异行进 EVENT_STOCKTAKE_VARIANCE,汇总进 EVENT_RECONCILE_DONE。
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from vela.db import current_session
from vela.domain.inventory.events import EVENT_RECONCILE_DONE
from vela.domain.inventory.stock_model import StockModel
from vela.domain.shared import make_event

SnapshotKey = tuple[int, str]
Snapshot = dict[SnapshotKey, int]


def take_snapshot(session: Session | None = None) -> Snapshot:
    """可用库存快照,键 (sku_id, warehouse)。"""
    session = session or current_session()
    stmt = select(StockModel)
    rows = session.execute(stmt).scalars()
    return {(s.sku_id, s.warehouse): s.available for s in rows}


def diff(snapshot_a: Snapshot, snapshot_b: Snapshot) -> list[dict]:
    """a 是期望值,b 是实际值。只返回对不上的行。"""
    out: list[dict] = []
    for key in sorted(set(snapshot_a) | set(snapshot_b), key=lambda k: (k[0], k[1])):
        expected = snapshot_a.get(key, 0)
        actual = snapshot_b.get(key, 0)
        if expected == actual:
            continue
        out.append(
            {
                "sku_id": key[0],
                "warehouse": key[1],
                "expected": expected,
                "actual": actual,
                "delta": actual - expected,
            }
        )
    return out


def emit_reconcile_event(diff_rows: list[dict], *, trace: str | None = None) -> dict:
    return make_event(
        EVENT_RECONCILE_DONE,
        {
            "count": len(diff_rows),
            "diff": diff_rows,
            "total_delta": sum(r["delta"] for r in diff_rows),
        },
        trace=trace,
    )
