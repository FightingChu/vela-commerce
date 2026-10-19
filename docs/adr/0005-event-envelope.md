# ADR-0005: 领域事件信封与版本化

状态: 提案(2026-06 提出,未排期)
关联代码: `vela/domain/shared/events.py`

## 背景

事件现在是裸 dict(type/payload/trace/occurred_at 四键约定)。
跨团队消费方已经开始按 payload 字段名强耦合,改一次字段就是一次事故。

## 提案

引入 `EventEnvelope`:

- 显式 `schema_version`,消费方按版本分支
- 携带 trace 与幂等 id,合并面收敛到 `merge_all` 一类方法
- 空合并结果用 `UNAVAILABLE` 哨兵,与"查询失败"区分

## 未决

- 老事件(裸 dict)兼容窗口多长
- 报表侧消费的 `EventBatch` 是否直接升级还是包一层适配
