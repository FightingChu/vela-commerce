"""审计包。

隐式上下文 + 多后端 sink,业务代码只碰 AuditService.record,
别的入口(直接写 AuditLogModel)都是历史遗留,别学。
"""

from vela.auditing.context import AuditContext, bind, child, current, redact, unbind
from vela.auditing.middleware import on_request_end, on_request_start
from vela.auditing.models import AuditLogModel
from vela.auditing.redaction import mask_amount, mask_id_card, mask_phone, redact_detail
from vela.auditing.service import AuditService
from vela.auditing.sink import DbSink, JsonlSink, MemorySink, Sink

__all__ = [
    "AuditContext",
    "AuditLogModel",
    "AuditService",
    "DbSink",
    "JsonlSink",
    "MemorySink",
    "Sink",
    "bind",
    "child",
    "current",
    "mask_amount",
    "mask_id_card",
    "mask_phone",
    "on_request_end",
    "on_request_start",
    "redact",
    "redact_detail",
    "unbind",
]
