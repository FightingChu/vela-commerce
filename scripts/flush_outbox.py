"""手工兜底:把 outbox 里积压的事件全部冲出去。

用法:
    python3 scripts/flush_outbox.py [--limit 100]

警告:和常驻 worker 并跑会互相抢活,先确认 worker 停了再用。
"""

from __future__ import annotations

import argparse
import sys


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=None, help="最多处理 N 条")
    args = parser.parse_args()

    # 延迟导入,--help 不吃数据库配置
    from vela.db.session import session_scope
    from vela.messaging.bus import EventBus
    from vela.messaging.dispatcher import flush_pending
    from vela.messaging.outbox import OutboxRepository

    with session_scope() as session:
        repo = OutboxRepository(session)
        n = flush_pending(repo, EventBus(), limit=args.limit)
    print(f"flushed {n} events")
    return 0


if __name__ == "__main__":
    sys.exit(main())
