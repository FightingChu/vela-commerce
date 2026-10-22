"""导出 audit_logs 为 JSONL,给合规导出和线下排查用。

用法:
    python3 scripts/dump_audit.py --out audit.jsonl
    python3 scripts/dump_audit.py --tenant main --since 2026-01-01 --action refund.approve
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tenant", default=None, help="按租户过滤(默认不过滤)")
    parser.add_argument("--since", default=None, help="YYYY-MM-DD,只导该时刻之后")
    parser.add_argument("--until", default=None, help="YYYY-MM-DD,只导该时刻之前")
    parser.add_argument("--actor", default=None, help="按操作人过滤")
    parser.add_argument("--action", default=None, help="按 action 前缀过滤")
    parser.add_argument("--out", default="-", help="输出文件,默认 stdout")
    parser.add_argument("--batch-size", type=int, default=1000)
    args = parser.parse_args()

    # 延迟导入,--help 不吃数据库配置
    from sqlalchemy import select

    from vela.auditing.models import AuditLogModel
    from vela.db.session import session_scope

    def _parse_day(value: str | None) -> dt.datetime | None:
        return dt.datetime.fromisoformat(value).replace(tzinfo=dt.timezone.utc) if value else None

    since = _parse_day(args.since)
    until = _parse_day(args.until)

    out = sys.stdout if args.out == "-" else open(args.out, "w", encoding="utf-8")  # noqa: SIM115 stdout 分支不能关
    total = 0
    try:
        with session_scope() as session:
            stmt = select(AuditLogModel).order_by(AuditLogModel.id)
            if args.tenant:
                stmt = stmt.where(AuditLogModel.tenant_id == args.tenant)
            if args.actor:
                stmt = stmt.where(AuditLogModel.actor == args.actor)
            if since is not None:
                stmt = stmt.where(AuditLogModel.created_at >= since)
            if until is not None:
                stmt = stmt.where(AuditLogModel.created_at < until)
            # yield_per 分批拉,全表导出别一次 load 进内存
            rows = session.execute(stmt, execution_options={"yield_per": args.batch_size}).scalars()
            for row in rows:
                if args.action and not row.action.startswith(args.action):
                    continue
                record = {
                    "id": row.id,
                    "tenant_id": row.tenant_id,
                    "created_at": row.created_at.isoformat() if row.created_at else None,
                    "actor": row.actor,
                    "action": row.action,
                    "target_type": row.target_type,
                    "target_id": row.target_id,
                    "detail": row.detail,
                    "trace": row.trace,
                }
                out.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
                total += 1
    finally:
        if out is not sys.stdout:
            out.close()

    print(f"dumped {total} audit rows", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
