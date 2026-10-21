# 部署手册

> 本文档面向运维与值班同学。应用侧改动请同步这里,CI 不会校验。

## 环境

| 环境 | 说明 | 配置入口 |
|---|---|---|
| dev | 本机/开发联调 | 默认,无需设置 |
| staging | 预发,数据同构脱敏 | `VELA_ENV=staging` |
| prod | 生产 | `VELA_ENV=prod` + 密钥管理注入 |

关键环境变量(完整清单见 `vela/config/settings.py`):

- `VELA_DB_URL` 主库连接串,必填(prod 由 KMS 注入,不要写进任何文件)
- `VELA_REPLICA_DB_URL` 只读副本,报表/导出走这里,没配回退主库
- `VELA_PORT` 默认 8300(2026-03 从 8200 迁移,LB 双挂期间老端口仍有效)
- `VELA_FEATURE_*` feature flag,默认全关,灰度名单在运维平台配

## 构建

```bash
docker build -t registry.internal/vela/vela-commerce:$(git rev-parse --short HEAD) .
```

镜像源由 CI 注入 `--build-arg`,不要在 Dockerfile 里写死(daocloud 拉取超时的事故见过两次)。

## 发布

滚动发布,k8s init container 跑 `alembic upgrade head`。
迁移注意:

1. 已上线迁移禁止修改,错误就加新迁移修正
2. 加列先 nullable 后回填再收紧,三步走,禁止一步到位
3. 大表加索引必须 `CREATE INDEX CONCURRENTLY`(手写迁移,autogenerate 出来的是阻塞版)

## 回滚

镜像回滚 + `alembic downgrade -1`(仅限未过 grace window 的迁移)。
超过 24h 的迁移默认不回滚,走前滚修复。

## 值班速查

- 8300 健康检查: `GET /healthz`,看 `db` 与 `bus` 两项
- outbox 堆积: `scripts/` 里的 flush 工具手工兜底(见 vela/messaging/dispatcher.py 文件头警告)
- 结算重复入账:#VT-2217 已修复(幂等键带 merchant scope),若仍有工单先核对版本是否 ≥ 修复提交
