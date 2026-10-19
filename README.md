# Vela Commerce(电商中台)

[![CI](https://github.com/FightingChu/vela-commerce/actions/workflows/ci.yml/badge.svg)](./.github/workflows/ci.yml)
![python](https://img.shields.io/badge/python-3.10%2B-blue)
![license](https://img.shields.io/badge/license-Proprietary-red)

Vela Retail 的电商中台服务。2024 年初从单体订单脚本起步,经历 2024-11 命名
标准化、2025Q1 领域化重构、2025Q3 事件总线落地三个大阶段,目前承担
订单、库存、价格、促销、结算五个核心域,以及报表导出、定时任务和三方
集成(支付/物流/短信/对象存储)。

**内部系统,未授权勿外传。**

## 架构总览

```
             ┌────────────────────────────────────────────┐
  HTTP 请求 → │ api/http (26 blueprints)  + schemas(22 DTO) │
             └──────────────────┬─────────────────────────┘
                                │
             ┌──────────────────▼─────────────────────────┐
             │ service/ 用例编排(checkout/查询/后台作业)   │
             └───┬──────────┬──────────┬──────────────────┘
                 │          │          │
     ┌───────────▼──┐ ┌─────▼─────┐ ┌──▼───────────┐
     │ domain/order │ │ inventory │ │ pricing/promotion │   ← 领域层(状态机/聚合/事件)
     │ settlement   │ │ customer  │ │                  │
     └───────────┬──┘ └─────┬─────┘ └──┬───────────┘
                 │          │          │
     ┌───────────▼──────────▼──────────▼───────────┐
     │ db(engine/session/repository/分片/租户)      │
     │ messaging(进程内总线 + outbox + worker)      │
     │ auditing / tenancy / integrations           │
     └─────────────────────────────────────────────┘
```

## 模块导览

| 目录 | 职责 | 说明 |
|---|---|---|
| `vela/domain/` | 领域层 | order(状态机/聚合/拆单/退款)、inventory(预占/扣减/对账)、pricing(价格簿/税率)、promotion(券/叠加规则)、settlement(账期/对账单)、customer |
| `vela/service/` | 用例编排 | checkout 全链路、订单查询视图、backoffice 导出/人工调整 |
| `vela/api/` | HTTP 层 | 26 个 blueprint(/api/v1/*),pydantic v2 DTO,全局错误映射 |
| `vela/jobs/` | 定时任务 | APScheduler 组装;预占超时/库存对账/结算推送/outbox 分发等 8 类 |
| `vela/reports/` | 报表导出 | 8 张内置报表 + CSV 流式导出(走只读副本) |
| `vela/integrations/` | 三方适配 | 支付/物流/短信/对象存储,默认路径零网络请求,统一重试与熔断 |
| `vela/messaging/` | 事件总线 | 进程内 pub/sub + outbox 表 + 同步/asyncio worker + 死信 |
| `vela/auditing/` | 审计 | 上下文、脱敏、落盘(Jsonl/DB) |
| `vela/tenancy/` | 多租户 | 解析、缓存键、查询过滤、注册表 |
| `vela/legacy/` | v1 遗留 | 只读,禁止新增需求,等审计 retention 评审(#VT-1503) |
| `alembic/` | 迁移 | 2024-06 → 2026-09 时间线,单链无分叉 |

## 快速开始

```bash
# 安装(建议 venv)
make install-dev

# 跑测试(384 条,内存 sqlite,无需外部依赖)
make test

# 起本地实例(0.0.0.0:8300)
make run

# 交互环境(session 已挂好)
make shell

# 数据库迁移
make migrate
```

环境变量见 `vela/config/settings.py` 顶部与 `docs/deploy.md`。
常用:`VELA_ENV`(dev/staging/prod)、`VELA_DB_URL`、`VELA_FEATURE_*`(默认全关)。

## API 示例

```bash
# 健康检查
curl localhost:8300/healthz

# 下单
curl -X POST localhost:8300/api/v1/checkout -H 'Content-Type: application/json' -d '{
  "customer_id": 42,
  "lines": [{"sku_id": 1001, "qty": 2}],
  "channel": "app"
}'

# 查单
curl localhost:8300/api/v1/orders/VL260101000001
```

完整路由见 `vela/api/http/`;错误码见 `docs/error-codes.md`。

## 开发约定

- 金额一律 `Decimal`,对外序列化为 str;禁止 float
- 时间一律 UTC 存储,展示层转本地时区(`vela/config/clocks.py`)
- 查询优先走 `Repository`,裸 select 必须手动套软删过滤(`not_deleted`)
- 新增错误码先在 `docs/error-codes.md` 登记
- 加列三步走(nullable → 回填 → 收紧),大表索引用 CONCURRENTLY
- 幂等键必须带 scope 构造(#VT-2217 的教训,settlement 域 README 有详述)

## 已知问题

- `#VT-2217` 结算单重推幂等键未带 scope,线上偶发重复入账(修复排期中)
- 分页 offset 超过 10w 性能塌方,游标方案在 `#VT-2140`,API 侧未切完
- `legacy/` 下 v1 代码冻结待删,依赖 retention 评审结论

## 文档

- 部署手册:[docs/deploy.md](docs/deploy.md)
- 架构决策:[docs/adr/](docs/adr/)(分片、事件信封、租户 scoping)
- 错误码:[docs/error-codes.md](docs/error-codes.md)
- 变更记录:[CHANGELOG.md](CHANGELOG.md)
