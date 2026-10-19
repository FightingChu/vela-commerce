"""超时预占释放。量级:正常每轮个位数,大促后第一轮可能上万。

释放动作(回补 available)在 reservation_repo.expire_due 里。
释放产生的事件挂 session.info,API 侧是中间件收走,job 进程没有
中间件,得自己 collect -> 落 outbox——2025-10 就因为漏了这步,
事件在 info 里攒到进程退出静默丢了(#VT-2088)。
"""

from __future__ import annotations

from vela.domain.inventory.reservation_service import release_expired
from vela.domain.inventory.stock_service import collect_events
from vela.jobs import context
from vela.jobs.messaging_bridge import drain_to_outbox
from vela.jobs.registry import register_job


@register_job("reservation_expire", trigger="每分钟")
def run(session=None) -> dict:
    with context.job_session(session) as s:
        released = release_expired(session=s)
        queued = drain_to_outbox(s, collect_events(s))
    return {"released": released, "events_queued": queued}
