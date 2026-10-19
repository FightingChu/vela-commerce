"""批量回填 tenant_id(单租户时代的存量表迁移到多租户用)。

用法:
    # 先预览,不动数据
    python3 scripts/backfill_tenant.py --dry-run
    # 正式回填到指定租户(默认 main)
    python3 scripts/backfill_tenant.py --tenant main --tables orders,refunds
    python3 scripts/backfill_tenant.py --tenant acme --batch-size 5000

分批 UPDATE,每批一个事务,避免大表一把梭把复制打挂。
对应迁移 e5f6a1b2c3d4 的第二步;新表(2025 起建表自带
tenant_id + server_default)不需要跑这个。
"""

from __future__ import annotations

import argparse
import sys

# 回填目标表。迁移链之外的表别乱加——加之前确认该表确实有
# tenant_id 列,不然 SQL 直接报错(也算一种保护)。
_TABLES = [
    "orders",
    "order_lines",
    "refunds",
    "customers",
    "addresses",
    "skus",
    "price_book_entries",
    "price_change_logs",
]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tenant", default="main", help="回填的租户标识(默认 main)")
    parser.add_argument("--tables", default=None, help="逗号分隔的表名,默认全部")
    parser.add_argument("--batch-size", type=int, default=2000, help="每批行数")
    parser.add_argument("--dry-run", action="store_true", help="只统计不动数据")
    args = parser.parse_args()

    # 延迟导入,--help 不吃数据库配置
    from sqlalchemy import text

    from vela.db.session import session_scope

    tables = args.tables.split(",") if args.tables else list(_TABLES)
    unknown = [t for t in tables if t not in _TABLES]
    if unknown:
        print(f"未知表(不回填): {', '.join(unknown)}", file=sys.stderr)
        return 2

    total = 0
    with session_scope() as session:
        for table in tables:
            # 表名来自白名单,不经过用户输入拼接
            rows = session.execute(
                text(f"SELECT COUNT(*) FROM {table} WHERE tenant_id IS NULL OR tenant_id = ''")
            ).scalar_one()
            if args.dry_run:
                print(f"[dry-run] {table}: {rows} 行待回填 -> {args.tenant}")
                total += rows
                continue
            done = 0
            while True:
                result = session.execute(
                    text(
                        f"UPDATE {table} SET tenant_id = :tenant "
                        "WHERE (tenant_id IS NULL OR tenant_id = '') "
                        "AND id IN ("
                        f"  SELECT id FROM {table} "
                        "  WHERE tenant_id IS NULL OR tenant_id = '' LIMIT :limit)"
                    ),
                    {"tenant": args.tenant, "limit": args.batch_size},
                )
                session.flush()
                session.commit()
                n = result.rowcount or 0
                done += n
                total += n
                if n < args.batch_size:
                    break
            print(f"{table}: 回填 {done} 行 -> {args.tenant}")

    if args.dry_run:
        print(f"[dry-run] 共 {total} 行待回填")
    return 0


if __name__ == "__main__":
    sys.exit(main())
