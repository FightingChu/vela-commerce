"""把 outbox 里的死信(DEAD)拨回 PENDING 重新投递。

用法:
    python3 scripts/requeue_dead.py                 # 全量死信
    python3 scripts/requeue_dead.py --limit 50      # 最多 50 条
    python3 scripts/requeue_dead.py --event-type order.paid --dry-run

先 --dry-run 看一眼死信原因(last_error)再决定,连环故障时
盲目重投只会把下游再打挂一次。
"""

from __future__ import annotations

import argparse
import sys


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=100, help="最多重投 N 条")
    parser.add_argument("--event-type", default=None, help="只重投指定事件类型")
    parser.add_argument("--dry-run", action="store_true", help="只列出,不修改")
    args = parser.parse_args()

    # 延迟导入,--help 不吃数据库配置
    from sqlalchemy import select

    from vela.db.session import session_scope
    from vela.messaging.queue_model import OutboxEventModel, OutboxStatus

    with session_scope() as session:
        stmt = (
            select(OutboxEventModel)
            .where(OutboxEventModel.status == OutboxStatus.DEAD)
            .order_by(OutboxEventModel.id)
            .limit(args.limit)
        )
        if args.event_type:
            stmt = stmt.where(OutboxEventModel.event_type == args.event_type)

        rows = list(session.execute(stmt).scalars())
        if not rows:
            print("没有死信,天下太平")
            return 0

        for row in rows:
            print(
                f"#{row.id} {row.event_type} attempts={row.attempts} "
                f"last_error={(row.last_error or '')[:120]}"
            )

        if args.dry_run:
            print(f"[dry-run] 共 {len(rows)} 条待重投")
            return 0

        for row in rows:
            row.status = OutboxStatus.PENDING
            row.attempts = 0
            row.next_retry_at = None
            row.last_error = None
        session.flush()
        print(f"重投 {len(rows)} 条死信 -> PENDING")
    return 0


if __name__ == "__main__":
    sys.exit(main())
