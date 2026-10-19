# Vela Commerce(电商中台)

Vela Retail 的电商中台服务,从 2024 年初的单体订单脚本一路演进到现在,
目前承担订单、库存、价格、促销、结算五个核心域,以及报表导出、定时任务
和三方集成(支付/物流/短信)。

**内部系统,未授权勿外传。**

## 快速开始

```bash
# 本地开发(建议 venv)
make install

# 跑测试
make test

# 起一个本地实例(默认 0.0.0.0:8300)
make run

# 数据库迁移
make migrate
```

## 目录

- `vela/domain/` 领域层(2025Q1 领域化重构的产物,之前都是 fat service)
- `vela/service/` 用例服务层
- `vela/api/` Flask blueprints + pydantic schemas
- `vela/jobs/` 定时与后台任务
- `vela/integrations/` 三方适配器(支付、物流、短信、对象存储)
- `vela/messaging/` 进程内事件总线 + asyncio worker
- `vela/legacy/` v1 遗留代码,只读,新需求一律不准往里加
- `alembic/` 迁移脚本(35 个,别手改已上线的)
- `tests/` 回归测试(核心域覆盖较好,部分老 handler 只有冒烟)

## 环境变量

见 `vela/config/settings.py` 顶部注释。常用:

- `VELA_ENV`: dev / staging / prod
- `VELA_DB_URL`: 主库连接串
- `VELA_FEATURE_*`: 各 feature flag,默认全关

## 已知问题

- `#VT-2217` 结算单重推时幂等键未带 scope,线上偶发重复入账(见 vela/domain/settlement/README)
- 分页 offset 超过 10w 性能塌方,报表导出先用了分批游标,API 侧还没改完
- legacy/sms v1 网关已停用但代码保留,等审计过 retention 才能删

## 部署

见 `docs/deploy.md`;镜像构建见 `Dockerfile`。CI 配置在 `.github/workflows/`。
