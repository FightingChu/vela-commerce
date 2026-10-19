"""调度器组装与一次性跑批。

build_scheduler 是常驻 job 进程的唯一入口(APScheduler 只在这里
实例化,模块 import 阶段不碰它,环境里没装也不影响单测)。
run_all_once 给部署后的冒烟检查和本地联调用,空库也应该全绿——
哪个 job 空库都跑不了,说明它偷偷假设了数据存在。

别和常驻 worker 进程并跑同一批 job,见 README。
"""

from __future__ import annotations

from typing import Iterable

from vela.config.logging import get_logger
from vela.config.settings import get_settings
from vela.jobs import config_defaults
from vela.jobs.registry import list_jobs, run_job

log = get_logger(__name__)


def build_scheduler(*, timezone: str | None = None):
    """按 config_defaults.DEFAULT_CRON 组装 BlockingScheduler。

    没配 cron 的 job 注册成 paused(apscheduler 3 里 next_run_time=None
    即暂停),启动日志里看得见,别静默漏跑。
    """
    from apscheduler.schedulers.blocking import BlockingScheduler
    from apscheduler.triggers.cron import CronTrigger

    tz = timezone or get_settings().timezone
    sched = BlockingScheduler(timezone=tz)
    for name in list_jobs():
        cron = config_defaults.cron_of(name)
        if cron is None:
            log.warning("job_without_cron", job=name)
            trigger = CronTrigger.from_crontab("0 6 31 2 *", timezone=tz)  # 2 月 31 日 = 永不
            paused = True
        else:
            trigger = CronTrigger.from_crontab(cron, timezone=tz)
            paused = False
        opts = dict(
            trigger=trigger,
            args=[name],
            id=name,
            name=name,
            max_instances=1,  # 上一轮没跑完不许叠,重入由 locks 再兜一层
            coalesce=True,
            misfire_grace_time=300,
            replace_existing=True,
        )
        if paused:
            opts["next_run_time"] = None  # apscheduler3 约定:None = 挂起
        sched.add_job(run_job, **opts)
    return sched


def run_all_once(names: Iterable[str] | None = None, **shared) -> dict[str, dict]:
    """把任务全量(或指定子集)各跑一遍,返回 名字 -> 结果 dict。

    shared 会透传给每个任务(测试塞 session 用)。单个任务失败不
    拦着后面的——护栏层已经把异常转成 {"ok": False} 了,这里只汇总。
    """
    targets = list(names) if names is not None else list_jobs()
    results: dict[str, dict] = {}
    for name in targets:
        results[name] = run_job(name, **shared)
    failures = [n for n, r in results.items() if not (r or {}).get("ok")]
    if failures:
        log.warning("run_all_once_partial_failure", failed=failures)
    return results
