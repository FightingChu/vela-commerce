# ADR-0006: 租户 scoping 显式化

状态: 讨论(2026-08 起,未定稿)
关联代码: `vela/db/tenant.py`、`vela/tenancy/`

## 背景

现状是"隐式"租户:中间件把租户塞进线程局部,Repository 基类自动过滤。
问题:

1. job/异步上下文里线程局部会丢,靠人肉补 `tenant_context()`
2. 自动过滤让"忘套过滤"的裸查询不易被发现(#VT-1987 事故的根因之一)

## 两个方向

- 方向 A: 全面显式化,所有查询传 `TenantScope` 对象,编译期可见
- 方向 B: 保持隐式 + 增加 lint 规则,裸 select 不带租户过滤就报错

## 倾向

倾向 A,但改动面大(所有 repository/service 签名),需要分域灰度。
`vela/tenancy/scoping.py` 的 `apply_tenant_filter` 是过渡期的折中:
显式调用,但不用改签名。
