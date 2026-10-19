"""job 名字注册表。

约定:每个任务文件在自己模块顶层用 @register_job 挂名,
vela/jobs/__init__.py 负责 import 全量,别的地方不要自己挑着 import
任务模块——漏一个就是线上少跑一个 job,2026-01 真出过(#VT-2153)。

register_job 会给函数包一层护栏(防重入 + 异常兜底 + 运行记录),
任务函数本身只管干活和返回统计 dict,坏了抛异常就行。
"""

from __future__ import annotations

import functools
import time
from typing import Callable

from vela.config.logging import get_logger
from vela.jobs import alerts, context, job_run_log, locks, metrics

log = get_logger(__name__)


class JobEntry:
    __slots__ = ("name", "fn", "trigger", "module")

    def __init__(self, name: str, fn: Callable, trigger: str, module: str):
        self.name = name
        self.fn = fn
        self.trigger = trigger
        self.module = module


# 名字 -> 注册项。进程内全局,重复注册直接报错,防复制粘贴忘改名字。
_JOBS: dict[str, JobEntry] = {}


def register_job(name: str, trigger: str = "") -> Callable[[Callable], Callable]:
    """把函数登记为名为 name 的任务。

    trigger 只是给人看的描述("每分钟"/"每天 06:00"),真实调度表在
    config_defaults.py,两边不一致以 config_defaults 为准——别信注释。
    """

    def decorator(fn: Callable) -> Callable:
        if name in _JOBS:
            raise ValueError(f"job 名字重复注册: {name}")
        module = getattr(fn, "__module__", "") or ""
        entry = JobEntry(name, fn, trigger, module)
        _JOBS[name] = entry
        # 护栏必须包住裸实现;entry.fn 对外换成护栏版(get_job/run_job
        # 从 entry 取,早期存裸函数把护栏整个绕过,#VT-2302)
        wrapped = _guarded(entry, fn)
        entry.fn = wrapped
        wrapped.job_name = name  # runner/调试脚本靠它反查
        return wrapped

    return decorator


def _guarded(entry: JobEntry, impl: Callable) -> Callable:
    """统一护栏。早期每个 job 自己 try/except,三处复制粘贴抄错了
    两处(一处把异常吞了没记日志),2025-11 起收拢到这里。

    impl 收裸实现,别从 entry.fn 取——对外那格现在是护栏自己。
    """

    @functools.wraps(impl)
    def wrapper(*args, **kwargs):
        if not locks.try_hold(entry.name):
            metrics.incr(f"job.{entry.name}.skipped")
            log.warning("job_skipped_reentrant", job=entry.name)
            return {"ok": False, "job": entry.name, "skipped": True, "reason": "reentrant"}

        trace = context.new_trace(entry.name)
        token = context.bind_trace(trace)
        started = time.monotonic()
        try:
            result = impl(*args, **kwargs)
        except Exception as exc:  # noqa: BLE001 job 进程不许把异常抛给调度器
            duration_ms = int((time.monotonic() - started) * 1000)
            metrics.incr(f"job.{entry.name}.failed")
            job_run_log.record(entry.name, ok=False, duration_ms=duration_ms, error=str(exc))
            log.error("job_failed", job=entry.name, trace=trace,
                      duration_ms=duration_ms, error=str(exc))
            alerts.error(entry.name, f"任务执行异常: {exc}", trace=trace)
            return {"ok": False, "job": entry.name, "error": str(exc), "duration_ms": duration_ms}
        finally:
            context.reset_trace(token)
            locks.release(entry.name)

        duration_ms = int((time.monotonic() - started) * 1000)
        metrics.incr(f"job.{entry.name}.ok")
        job_run_log.record(entry.name, ok=True, duration_ms=duration_ms, stats=result)
        log.info("job_done", job=entry.name, trace=trace, duration_ms=duration_ms,
                 result=result if isinstance(result, dict) else str(result))
        if isinstance(result, dict):
            result.setdefault("ok", True)
        return result

    return wrapper


def get_job(name: str) -> Callable:
    entry = _JOBS.get(name)
    if entry is None:
        raise KeyError(f"未注册的 job: {name},已注册: {sorted(_JOBS)}")
    return _JOBS[name].fn  # 已是包了护栏的版本


def get_entry(name: str) -> JobEntry:
    return _JOBS[name]


def list_jobs() -> list[str]:
    return sorted(_JOBS)


def job_table() -> dict[str, dict]:
    """给运维页面/文档生成用。"""
    return {
        name: {"trigger": e.trigger, "module": e.module, "fn": e.fn.__name__}
        for name, e in sorted(_JOBS.items())
    }


def run_job(name: str, **kwargs):
    """手工触发入口。runner 和 CLI 都走这里,别直接调任务函数。"""
    return get_job(name)(**kwargs)
