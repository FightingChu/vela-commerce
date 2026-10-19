# 错误码登记表

新错误码先在这里登记,再在 `vela/config/errors.py` 落地。
HTTP 层映射见 `vela/api/http/errors.py`(M2 落地后生效)。

| code | 异常 | HTTP | 说明 |
|---|---|---|---|
| vela.0000 | VelaError | 500 | 兜底,出现即 bug |
| vela.0101 | ConfigError | 500 | 配置缺失/非法 |
| vela.0201 | ValidationError | 400 | 入参校验失败 |
| vela.0404 | NotFoundError | 404 | 资源不存在 |
| vela.0409 | ConflictError | 409 | 业务冲突(唯一键/状态) |
| vela.0410 | ConcurrencyError | 409 | 乐观锁冲突,建议重试 |
| vela.0422 | TenantError | 403 | 租户越权/缺失 |
| vela.0502 | ExternalServiceError | 502 | 三方依赖异常 |
| inventory.0409 | InventoryShortageError | 409 | 库存不足 |
| order.* | OrderStateError 等 | 409/404 | 订单域内码 |

约定:

- detail 字段只放排查需要的结构化信息,**禁止**放敏感数据(手机号、卡号),审计侧有 redact 兜底但别依赖它
- code 一经发布不可变更语义,废弃就标注 deprecated 并保留半年
