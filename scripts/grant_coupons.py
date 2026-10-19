"""批量发券:一次生成一批同规格券码,给运营投放用。

用法:
    # 100 张满 100 减 20 的券,码前缀 NY2026
    python3 scripts/grant_coupons.py --kind THRESHOLD \
        --threshold 100 --discount 20 --count 100 --prefix NY2026 \
        --title "新年满减券" --quota 500

    # 先预览生成的券码
    python3 scripts/grant_coupons.py --kind NO_THRESHOLD --discount 5 \
        --count 10 --prefix TEST --dry-run

kind 三选一:THRESHOLD(满减)/ DISCOUNT(折扣,给 --rate 0.15)/
NO_THRESHOLD(无门槛直减)。GIFT / FREE_SHIPPING 已下线,不支持。
"""

from __future__ import annotations

import argparse
import sys
import uuid


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kind", required=True,
                        choices=["THRESHOLD", "DISCOUNT", "NO_THRESHOLD"])
    parser.add_argument("--title", required=True, help="券名,展示用")
    parser.add_argument("--count", type=int, default=1, help="生成张数")
    parser.add_argument("--prefix", default="VELA", help="券码前缀")
    parser.add_argument("--threshold", type=float, default=0.0, help="THRESHOLD 的门槛金额")
    parser.add_argument("--discount", type=float, default=0.0,
                        help="抵扣金额(THRESHOLD / NO_THRESHOLD 用)")
    parser.add_argument("--rate", type=float, default=0.0,
                        help="折扣率小数,0.15 = 8.5 折(DISCOUNT 用)")
    parser.add_argument("--quota", type=int, default=100, help="单券总核销额度")
    parser.add_argument("--per-customer-limit", type=int, default=1)
    parser.add_argument("--tenant", default=None, help="租户,默认取当前上下文")
    parser.add_argument("--valid-to", default=None, help="YYYY-MM-DD,有效期止")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    # 延迟导入,--help 不吃数据库配置
    import datetime as dt

    from vela.config.clocks import utc_now
    from vela.db.session import session_scope
    from vela.domain.promotion.coupon_model import CouponKind, CouponModel
    from vela.domain.shared import to_decimal

    if args.kind == "DISCOUNT" and args.rate <= 0:
        print("DISCOUNT 必须给 --rate", file=sys.stderr)
        return 2
    if args.kind == "THRESHOLD" and (args.threshold <= 0 or args.discount <= 0):
        print("THRESHOLD 必须给 --threshold 和 --discount", file=sys.stderr)
        return 2
    if args.kind == "NO_THRESHOLD" and args.discount <= 0:
        print("NO_THRESHOLD 必须给 --discount", file=sys.stderr)
        return 2

    # kind 是 StrEnumColumn,直接塞枚举,落库存的是 name
    kind = CouponKind[args.kind]
    valid_to = (
        dt.datetime.fromisoformat(args.valid_to).replace(tzinfo=dt.timezone.utc)
        if args.valid_to else None
    )

    codes = [f"{args.prefix}-{uuid.uuid4().hex[:12].upper()}" for _ in range(args.count)]
    if args.dry_run:
        for code in codes:
            print(f"[dry-run] {code} {args.kind}")
        return 0

    kwargs = {}
    if args.tenant:
        kwargs["tenant_id"] = args.tenant

    with session_scope() as session:
        for code in codes:
            session.add(
                CouponModel(
                    code=code,
                    title=args.title,
                    kind=kind,
                    threshold_amount=to_decimal(args.threshold),
                    discount_amount=to_decimal(args.discount),
                    discount_rate=to_decimal(args.rate),
                    total_quota=args.quota,
                    per_customer_limit=args.per_customer_limit,
                    valid_from=utc_now(),
                    valid_to=valid_to,
                    enabled=True,
                    **kwargs,
                )
            )
        session.flush()
    print(f"生成 {len(codes)} 张券,前缀 {args.prefix}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
