"""账期巡检:列出逾期未结算的 settlement 单,给财务催收 job 用。

用法:
    python3 scripts/check_overdue.py --limit 50
    python3 scripts/check_overdue.py --json    # 机器可读输出,喂告警平台
    python3 scripts/check_overdue.py --days-grace 3

口径:due_date = confirmed_at + terms_days(见
vela/domain/settlement/terms.py),与 #VT-2148 定的口径一致;
宽限期只影响本脚本的展示,不改账期数据。
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=100, help="最多列 N 条")
    parser.add_argument("--days-grace", type=int, default=0, help="宽限期天数")
    parser.add_argument("--json", action="store_true", dest="as_json", help="JSON 输出")
    args = parser.parse_args()

    # 延迟导入,--help 不吃数据库配置
    from vela.config.clocks import utc_now
    from vela.db.session import session_scope
    from vela.domain.settlement.repository import SettlementRepository
    from vela.domain.settlement.terms import due_date

    now = utc_now()
    cutoff = now - dt.timedelta(days=args.days_grace)

    with session_scope() as session:
        # repository 里自带 list_overdue,别在脚本里裸 select 重写口径
        rows = SettlementRepository(session).list_overdue(cutoff, limit=args.limit)

        payload = []
        for row in rows:
            due = due_date(row.confirmed_at, row.terms_days) if row.confirmed_at else None
            overdue_days = (now - due).days if due else None
            payload.append(
                {
                    "settlement_sn": row.settlement_sn,
                    "merchant_id": row.merchant_id,
                    "tenant_id": row.tenant_id,
                    "status": row.status,
                    "due_date": due.isoformat() if due else None,
                    "overdue_days": overdue_days,
                    "net_amount": str(row.net_amount),
                }
            )

    if args.as_json:
        print(json.dumps({"checked_at": now.isoformat(), "rows": payload}, ensure_ascii=False, indent=2))
    else:
        if not payload:
            print("无逾期结算单")
            return 0
        print(f"{'settlement_sn':<26}{'merchant':>9}{'逾期天数':>6}  net_amount")
        for item in payload:
            print(
                f"{item['settlement_sn']:<26}{item['merchant_id']:>9}"
                f"{item['overdue_days'] or 0:>7}  {item['net_amount']}"
            )
        print(f"共 {len(payload)} 条逾期(宽限 {args.days_grace} 天)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
