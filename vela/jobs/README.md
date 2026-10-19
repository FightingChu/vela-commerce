# vela/jobs 定时任务

## 这个包是什么

中台所有周期任务的集合。每个任务一个文件,函数只管干活、返回统计
dict;注册、防重入、异常兜底、运行记录统一在 registry.py 的护栏里,
新任务不要自己写 try/except——2025-11 之前每个 job 各自兜异常,
三处复制粘贴抄错两处,其中一处把异常吞了没日志,查了一晚上。

## 怎么跑

- 常驻:部署脚本的 job 进程入口就是
  `python -c "from vela.jobs import build_scheduler; build_scheduler().start()"`。job 进程单实例部署,别起多个。
- 冒烟:`run_all_once()`,空库也应该全绿。

**别和常驻 worker 并跑同一批任务。** 现在的防重入(locks.py)是
进程内存版,挡不住跨进程;两个进程同时跑 stock_reconcile 会出
双份对账事件,运营的周报就多一倍差异行。之前出过一次,排查半天
才发现是 k8s 滚动发布时新旧 pod 共存了几分钟(#VT-2107)。滚动
发布时旧 pod 要等当前任务跑完再退(APScheduler 的 shutdown(wait=True))。

## 约定

- 调度表只认 config_defaults.DEFAULT_CRON,任务文件里 trigger
  参数是给人看的注释,两边不一致时以 DEFAULT_CRON 为准。
- 任务返回 dict,字段用小写下划线;护栏会往里塞 ok 字段。
- 事件落 outbox 走 messaging_bridge.drain_to_outbox,别自己
  enqueue(API 侧才是中间件收)。
- DB 会话用 context.job_session,测试里直接塞 session。

## 已知欠账

- locks.py 的 Redis 版:#VT-2190
- 对账快照落库:#VT-2247
- 运行记录落库:#VT-2209(排过两次都被插队)
- job 执行历史页面:等运行记录落库之后
