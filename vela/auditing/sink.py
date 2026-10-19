"""审计落盘后端。选型看部署形态:单机 job 用 JsonlSink,
服务进程走 DbSink,MemorySink 只给测试和 debug。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Protocol, runtime_checkable

from vela.db import current_tenant


@runtime_checkable
class Sink(Protocol):
    def write(self, record: dict) -> None:
        """record 字段约定见 AuditService.record,dict 结构别乱加键。"""
        ...


class JsonlSink:
    """追加写 jsonl 文件,轮转交给 logrotate,进程内不管。"""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        # 目录不存在就建,job 容器里 /var/log/vela 不一定有
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def write(self, record: dict) -> None:
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")


class MemorySink:
    """测试用,顺便给本地 debug 脚本看最近写了什么。"""

    def __init__(self) -> None:
        self.records: list[dict] = []

    def write(self, record: dict) -> None:
        self.records.append(record)


class DbSink:
    """写审计表。tenant 兜底取当前租户上下文,历史 job 没显式给过。"""

    def __init__(self, session):
        self.session = session

    def write(self, record: dict) -> None:
        # 延迟 import,避免 models -> service -> sink 的循环
        from vela.auditing.models import AuditLogModel

        self.session.add(
            AuditLogModel(
                actor=record["actor"],
                action=record["action"],
                target_type=record["target_type"],
                target_id=str(record["target_id"]),
                detail=record.get("detail"),
                trace=record.get("trace"),
                tenant_id=record.get("tenant") or current_tenant(),
            )
        )
