"""凌晨库存对账:当前快照 vs 上一轮快照,差异进 outbox。

上一轮快照存进程内存——job 进程单实例常驻,重启后第一轮拿空
期望值,会把全量库存当差异报一遍,凌晨三点吵一次。接受的:
宁可误报不能漏报,落库方案(#VT-2247)排到下个迭代了。
"""

from __future__ import annotations

from vela.domain.inventory import reconcile
from vela.jobs import context
from vela.jobs.registry import register_job

# (sku_id, warehouse) -> available。见模块注释,内存版是有意的。
_LAST_SNAPSHOT: reconcile.Snapshot | None = None


@register_job("stock_reconcile", trigger="每天 03:15")
def run(session=None) -> dict:
    global _LAST_SNAPSHOT
    with context.job_session(session) as s:
        current = reconcile.take_snapshot(session=s)
        if _LAST_SNAPSHOT is None:
            # 第一轮(或重启后第一轮)只建基线不报警
            rows: list[dict] = []
            baseline = True
        else:
            rows = reconcile.diff(_LAST_SNAPSHOT, current)
            baseline = False
        _LAST_SNAPSHOT = current

        event = reconcile.emit_reconcile_event(rows, trace=context.current_trace())
        from vela.jobs.messaging_bridge import drain_to_outbox

        queued = drain_to_outbox(s, [event])

    return {
        "baseline": baseline,
        "sku_wh_pairs": len(current),
        "variance_rows": len(rows),
        "total_delta": sum(r["delta"] for r in rows),
        "events_queued": queued,
    }
