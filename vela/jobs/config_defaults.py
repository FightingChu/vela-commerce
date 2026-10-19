"""默认调度表。时间一律服务器本地(Asia/Shanghai),别写 UTC。

改这里之前先看运维值班表:03:15 对账和 03:30 的 binlog 备份
挤在一起出过磁盘抖动,低谷时段很挤,新任务尽量往白天塞。
"""

from __future__ import annotations

# job 名 -> cron 表达式(5 段,分 时 日 月 周)。
# 新任务三件事:任务文件 @register_job、__init__.py 加 import、
# 这里加一行。少一行就是线上少跑一个 job(#VT-2153)。
DEFAULT_CRON: dict[str, str] = {
    # 高频兜底类
    "reservation_expire": "*/1 * * * *",
    "outbox_dispatch": "*/1 * * * *",
    "dead_letter_sweep": "*/10 * * * *",
    # 白天运营类
    "settlement_push": "0 7 * * *",
    # 凌晨重活类
    "coupon_expire": "5 0 * * *",
    "stock_reconcile": "15 3 * * *",
    "audit_archive": "0 5 * * *",
    "tier_recalculate": "30 4 * * 1",
}


def cron_of(name: str) -> str | None:
    return DEFAULT_CRON.get(name)
