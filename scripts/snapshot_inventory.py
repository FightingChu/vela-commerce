"""库存快照:导出 (sku_id, warehouse) -> available 到 JSON 文件。

用法:
    python3 scripts/snapshot_inventory.py --out snap.json
    python3 scripts/snapshot_inventory.py            # 打印到 stdout

配合 reconcile.diff 做对账:今天一份、明天一份,或拿盘点导入的
期望值 diff。凌晨 job 的图形入口,人工兜底也用它。
"""

from __future__ import annotations

import argparse
import json
import sys


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default="-", help="输出 JSON 文件,默认 stdout")
    args = parser.parse_args()

    # 延迟导入,--help 不吃数据库配置
    from vela.db.session import session_scope
    from vela.domain.inventory.reconcile import take_snapshot

    with session_scope() as session:
        snapshot = take_snapshot(session)

    # 键序列化成 "sku_id:warehouse",diff 侧自己拆回来
    payload = {
        "taken_at": None,  # take_snapshot 不带时间,落盘时补
        "rows": {f"{sku_id}:{warehouse}": available for (sku_id, warehouse), available in sorted(snapshot.items())},
    }
    from vela.config.clocks import utc_now

    payload["taken_at"] = utc_now().isoformat()

    text = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.out == "-":
        print(text)
    else:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(text + "\n")
        print(f"snapshot: {len(snapshot)} rows -> {args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
