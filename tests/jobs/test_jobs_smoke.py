"""jobs 冒烟:全量可 import、注册表与调度表对齐、空库 run_all_once 全绿。

原则:哪个 job 空库跑不了,说明它偷偎假设了数据存在,红灯拦在 CI。
"""

from __future__ import annotations

import pytest

import vela.jobs
from vela.jobs import config_defaults

# 全量任务清单。加任务忘了改这里,冒烟会提醒你补 cron/import
EXPECTED_JOBS = frozenset(
    {
        "reservation_expire",
        "stock_reconcile",
        "settlement_push",
        "outbox_dispatch",
        "dead_letter_sweep",
        "coupon_expire",
        "tier_recalculate",
        "audit_archive",
    }
)


def test_all_job_modules_importable():
    # import vela.jobs 已经把任务模块全量挂了;这里验清单
    assert set(vela.jobs.list_jobs()) == EXPECTED_JOBS


def test_cron_table_covers_all_jobs():
    # 调度表和注册表必须一一对应,缺一边都是事故(#VT-2153)
    assert set(config_defaults.DEFAULT_CRON) == set(vela.jobs.list_jobs())


def test_cron_expressions_are_parseable():
    from apscheduler.triggers.cron import CronTrigger

    for name, cron in config_defaults.DEFAULT_CRON.items():
        CronTrigger.from_crontab(cron)  # 解析不了直接炸
        assert len(cron.split()) == 5, f"{name} 的 cron 必须是 5 段"


def test_run_all_once_on_empty_db(db_session):
    results = vela.jobs.run_all_once(session=db_session)
    assert set(results) == EXPECTED_JOBS
    for name, result in results.items():
        assert result is not None, name
        # 护栏层塞的 ok 标记:一个都不能红
        assert result.get("ok") is True, f"{name}: {result}"


def test_run_job_by_name(db_session):
    result = vela.jobs.run_job("reservation_expire", session=db_session)
    assert result["ok"] is True
    assert result["released"] == 0


def test_unknown_job_raises_keyerror():
    with pytest.raises(KeyError):
        vela.jobs.run_job("no_such_job")


def test_run_log_records_after_run(db_session):
    from vela.jobs import job_run_log, metrics

    vela.jobs.run_job("coupon_expire", session=db_session)
    last = job_run_log.last_run("coupon_expire")
    assert last is not None and last["ok"] is True
    assert metrics.get("job.coupon_expire.ok") >= 1


def test_locks_prevent_reentry(db_session, monkeypatch):
    """手工触发撞上正在跑的 cron:第二个拿锁失败,返回 skipped。"""
    from vela.jobs import locks

    locks.reset()
    try:
        assert locks.try_hold("coupon_expire") is True
        result = vela.jobs.run_job("coupon_expire", session=db_session)
        assert result.get("skipped") is True
        assert locks.held("coupon_expire") is True
    finally:
        locks.release("coupon_expire")
    # 释放后又能抢了
    assert locks.try_hold("coupon_expire") is True
    locks.release("coupon_expire")


def test_locks_expire_after_ttl(monkeypatch):
    import vela.jobs.locks as locks_mod

    locks_mod.reset()
    try:
        assert locks_mod.try_hold("x", ttl_seconds=10) is True
        # 把过期时刻拨到过去,模拟卡死的锁到点释放
        locks_mod._HOLD["x"] -= 11
        assert locks_mod.try_hold("x", ttl_seconds=10) is True
    finally:
        locks_mod.reset()


def test_guarded_job_swallows_exception():
    """任务抛异常不冒泡,转成 {"ok": False} 并记运行日志。"""
    from vela.jobs import job_run_log
    from vela.jobs.registry import register_job

    @register_job("_smoke_boom", trigger="仅测试")
    def boom(session=None):  # noqa: ARG001
        raise RuntimeError("炸给护栏看")

    try:
        result = vela.jobs.run_job("_smoke_boom")
        assert result["ok"] is False
        assert "炸给护栏看" in result["error"]
        assert job_run_log.last_run("_smoke_boom")["ok"] is False
    finally:
        # 测试注册项别漏到别的用例
        from vela.jobs.registry import _JOBS

        _JOBS.pop("_smoke_boom", None)


def test_build_scheduler_registers_all_jobs():
    """APScheduler 只在 build_scheduler 里实例化,这里顺带验装配。"""
    from apscheduler.triggers.cron import CronTrigger

    sched = vela.jobs.build_scheduler()
    try:
        jobs = sched.get_jobs()
        assert {j.id for j in jobs} == EXPECTED_JOBS
        # 全部是 cron 触发器(未 start 的调度器上看不到 next_run_time)
        assert all(isinstance(j.trigger, CronTrigger) for j in jobs)
    finally:
        # 没 start 过的 BlockingScheduler 调 shutdown 会抛
        # SchedulerNotRunningError,直接丢给 GC 就行
        pass
