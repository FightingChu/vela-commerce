# ADR-0006: 租户 scoping 过渡方案

状态: 已采纳(2026-10)
关联代码: `vela/db/tenant.py`、`vela/tenancy/`

## 背景

租户最初是"隐式":中间件把租户塞进线程局部,Repository 基类自动过滤。
job/异步上下文里线程局部会丢,靠人肉补 `tenant_context()`;
裸查询忘套过滤也不易发现(#VT-1987 事故的根因之一)。

## 决策

分两步走,当前处于第一步:

1. **过渡期(现行)**:`vela/tenancy/scoping.py` 提供 `apply_tenant_filter`,
   显式调用、不改 repository 签名;列存在性检查让无租户列的表自然跳过。
   导出/删除类高危操作强制显式租户(`tenancy/guard.py`)。
2. **目标态**:全面显式化,查询传 `TenantScope` 对象,分域灰度迁移。
   迁移从 settlement 域开始(它已要求显式租户的导出)。

## 后果

- 新写的裸 select 一律手动套 `apply_tenant_filter`,review 必查项
- 线程局部机制保留,但只作为 api 中间件的注入点,不再被业务代码直接依赖
