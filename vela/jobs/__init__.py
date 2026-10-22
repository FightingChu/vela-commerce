"""定时任务包。

入口两个:runner.build_scheduler(常驻进程)和 runner.run_all_once
(冒烟/联调)。调度表在 config_defaults.DEFAULT_CRON。

新任务四件事,缺一不可:
  1. 建任务文件,函数上 @register_job("名字", trigger="给人看的描述")
  2. 函数只管干活,返回统计 dict;异常尽管抛,护栏层统一兜
  3. 本文件末尾加 import(注册靠 import 副作用,别挑着 import——
     少 import 一个就是线上少跑一个 job,#VT-2153)
  4. config_defaults.DEFAULT_CRON 加一行 cron
"""

# ---- 全量挂载任务模块(注册靠 import 副作用) ----
from vela.jobs import (  # noqa: F401
    audit_archive,
    coupon_expire,
    dead_letter_sweep,
    messaging_bridge,
    outbox_dispatch,
    reservation_expire,
    settlement_push,
    stock_reconcile,
    tier_recalculate,
)
from vela.jobs.context import JobContext, current_trace, job_session
from vela.jobs.registry import (
    get_entry,
    get_job,
    job_table,
    list_jobs,
    register_job,
    run_job,
)
from vela.jobs.runner import build_scheduler, run_all_once

__all__ = [
    "JobContext",
    "build_scheduler",
    "current_trace",
    "get_entry",
    "get_job",
    "job_session",
    "job_table",
    "list_jobs",
    "register_job",
    "run_all_once",
    "run_job",
]
