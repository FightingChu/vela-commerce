"""逾期结算单推送。每天 07:00 一轮,推完事件进 outbox 给渠道侧。

只推 CONFIRMED 状态的:DRAFT 是商户还没对完账,推了也要被打回;
FAILED 的走人工重置,自动化别碰(2025-08 自动重推把费率算错的
一批单推给了渠道,撤回流程走了一周,#VT-1976)。
"""

from __future__ import annotations

from vela.config.clocks import utc_now
from vela.config.logging import get_logger
from vela.domain.settlement.repository import SettlementRepository
from vela.domain.settlement.service import SettlementService
from vela.domain.settlement.states import SettlementStatus
from vela.jobs import alerts, context
from vela.jobs.messaging_bridge import drain_to_outbox
from vela.jobs.registry import register_job

log = get_logger(__name__)


@register_job("settlement_push", trigger="每天 07:00")
def run(session=None, *, limit: int = 200) -> dict:
    with context.job_session(session) as s:
        repo = SettlementRepository(s)
        service = SettlementService(s)
        overdue = repo.list_overdue(utc_now(), limit=limit)

        pushed, skipped, failed = 0, 0, 0
        events: list[dict] = []
        for model in overdue:
            if model.settlement_status != SettlementStatus.CONFIRMED:
                skipped += 1
                continue
            try:
                events.append(service.push(model.settlement_sn))
                pushed += 1
            except Exception as exc:  # 单笔失败不拦整批
                failed += 1
                log.warning("settlement_push_row_failed",
                            settlement_sn=model.settlement_sn, error=str(exc))

        queued = drain_to_outbox(s, events)

    if failed:
        alerts.warn("settlement_push", f"逾期结算单推送失败 {failed} 笔", failed=failed)
    return {
        "overdue": len(overdue),
        "pushed": pushed,
        "skipped": skipped,
        "failed": failed,
        "events_queued": queued,
    }
