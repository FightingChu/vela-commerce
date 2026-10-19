"""job 进程和 messaging 层的桥。

API 侧事件由 http 中间件统一收进 outbox,job 进程没有中间件。
以前每个 job 自己写一遍 collect + enqueue,三个任务抄出三种写法
(有一个把 trace 丢了),2026-02 收拢到这里。
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from vela.messaging.outbox import OutboxRepository


def drain_to_outbox(session: Session, events: list[dict]) -> int:
    """把 make_event 产的事件批量塞进 outbox,返回条数。

    事件里若混进了不合法的 dict,这里直接抛——护栏层会兜住并报警,
    事件静默丢比 job 红一次严重得多。
    """
    if not events:
        return 0
    repo = OutboxRepository(session)
    for ev in events:
        repo.enqueue(ev["type"], ev.get("payload"), trace=ev.get("trace"))
    return len(events)
