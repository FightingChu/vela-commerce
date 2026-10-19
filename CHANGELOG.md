# Changelog

格式参考 Keep a Changelog;2025 年前没记,凭 git log 考古。

## [1.4.0] - 2026-10

### Added

- api 层:26 个 blueprint(/api/v1)、pydantic v2 DTO、create_app 工厂与全局错误映射
- service 用例层:checkout 编排、订单查询视图、backoffice 导出与人工调整
- jobs:APScheduler 组装,8 类定时任务(预占超时/库存对账/结算推送/outbox 分发等)
- reports:8 张内置报表 + CSV 流式导出
- integrations:支付/物流/短信/对象存储适配器(默认零网络请求)
- messaging:outbox 死信、asyncio worker、令牌桶背压
- alembic 迁移时间线补齐(12 个,单链)
- CI(ci.yml/release.yml)与运维脚本 8 个

### Fixed

- `vela/db/session.py` session_scope 缺 contextmanager(2026-10 发现,api 层联装时炸出)
- logging 不支持结构化 kwargs,VelaLogger 统一收进 extra
- settlement 幂等查重按 merchant_id 和完整 token 限定，修复 #VT-2217 跨商户误拦与相似 token 误命中

## [1.3.0] - 2026-09

### Added

- 多租户 tenancy 包(解析/缓存键/查询过滤/注册表)
- Feature flag:tenant_sharding(默认关,ADR-0003)

## [1.2.0] - 2026-03

### Changed

- 服务端口 8200 → 8300,LB 双挂迁移一个月

### Added

- 报表导出走只读副本;导出行数上限 max_export_rows

## [1.1.0] - 2025-09

### Added

- inventory 预占凭证化(部分释放受 flag `inventory_partial_release` 控制)
- outbox 模式落地,事件先落库再分发

## [1.0.0] - 2025-04

### Changed

- 领域化重构收尾:fat service 拆入 domain/,老 fetch_ 命名开始统一(未清完)

## [0.x] - 2024

- 单体订单脚本起步;2024-11 表命名标准化迁移(当时踩了一堆 rename 坑,见 git log)
