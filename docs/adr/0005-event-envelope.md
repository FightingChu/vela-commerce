# ADR-0005: 领域事件信封与版本化

状态: 已采纳(2026-10)
关联代码: `vela/domain/shared/events.py`

## 背景

事件最初是裸 dict(type/payload/trace/occurred_at 四键约定),
跨团队消费方按 payload 字段名强耦合,改一次字段就是一次事故。

## 决策

- 合并面收敛到 `EventBatch.merge_all` 一类方法,消费方不自行拼装统计
- 空合并结果用 `UNAVAILABLE` 哨兵区分"没数据"和"查询失败",
  对账/报表侧统一按哨兵分支
- 事件分发统一走 outbox 先落库再投递(messaging 包),进程内总线只做进程内分发
- schema 版本化分两步:先固定四键约定,消费方按 type 前缀分域;
  payload 内字段演进走"只加不改不删",破坏性变更换新 type

## 后果

- 老的裸 dict 构造点已全部迁到 `make_event`,新代码不允许手拼 dict
- 哨兵是 dict 拷贝不是 None,消费方判空要用相等比较,`vela/messaging/filters.py`
  提供了 `drop_unavailable` 兜底
