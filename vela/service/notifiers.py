"""事件出口。同步总线(本进程)和 outbox(跨进程)在这里一起发。

2025-11 之前只有总线,job 重启就丢事件;只有 outbox 又没法给同进程
的报表聚合实时喂数。现在两个都发是过渡姿势,等 dispatcher 稳定后
业务侧只调 fanout,别的别碰。
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from vela.messaging import get_bus
from vela.messaging.outbox import OutboxRepository
from vela.domain.shared.events import payload_of


def publish_to_bus(event: dict) -> int:
    """进程内分发。没人订阅返回 0,不算错误。"""
    return get_bus().publish(event)


def enqueue_outbox(session: Session, event: dict):
    """事件入 outbox,随业务事务一起提交。trace 用事件自带的。"""
    return OutboxRepository(session).enqueue(
        event["type"],
        event.get("payload", {}),
        trace=event.get("trace"),
    )


def fanout(session: Session, events: list[dict]) -> int:
    """总线 + outbox 双发。返回入 outbox 的条数(总线的分发数不好统计)。"""
    for event in events:
        publish_to_bus(event)
        enqueue_outbox(session, event)
    return len(events)


def event_field(event: dict, key: str, default=None):
    """读 payload 字段的小 convenience,免得各处 event["payload"][...]。"""
    return payload_of(event, key, default)
