"""审计桥。admin/backoffice 操作在这里统一落审计,业务模块别各自
new AuditService——sink 的选择(内存/DB/jsonl)以后要收口到配置。

没绑 AuditContext 也能用(AuditService 自己降级成 system actor),
但导出类操作建议调用方先 bind,不然审计里查不到是谁干的。
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from vela.auditing.service import AuditService
from vela.auditing.sink import Sink
from vela.config.logging import get_logger

log = get_logger(__name__)


def bridge(session: Session, sink: Sink | None = None) -> AuditService:
    """拿一个绑定了 session 的审计服务。同一请求内反复调用开销可忽略
    (sink 每次重建,量大了再缓存)。"""
    return AuditService(session, sink=sink)


def record_admin_action(
    session: Session,
    action: str,
    target_type: str,
    target_id,
    detail: dict | None = None,
    *,
    sink: Sink | None = None,
) -> dict:
    """管理端动作统一入口。返回落盘的 record,调用方要断言就直接用。"""
    service = bridge(session, sink=sink)
    record = service.record(action, target_type, target_id, detail)
    log.info(
        "admin_action_recorded",
        action=action,
        target_type=target_type,
        target_id=str(target_id),
    )
    return record


def record_events_as_audit(session: Session, events: list[dict]) -> int:
    """把领域事件批量转成审计记录。动作名用事件 type,target 从
    payload 里猜(order_sn/settlement_sn/...),猜不到记 None。

    这是个兜底通道:正经审计点还是应该在业务动作处显式记。
    """
    count = 0
    for event in events:
        payload = event.get("payload", {})
        target_id = (
            payload.get("order_sn")
            or payload.get("settlement_sn")
            or payload.get("refund_sn")
        )
        record_admin_action(
            session,
            action=event.get("type", "unknown.event"),
            target_type="event",
            target_id=target_id,
            detail=payload,
        )
        count += 1
    return count
