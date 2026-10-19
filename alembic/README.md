# alembic 迁移目录

## 生成一个迁移

```bash
# 先确认 VELA_DB_URL 指向你的开发库
export VELA_DB_URL=postgresql://vela:xxx@localhost:5432/vela

# 手写(推荐,autogenerate 对 check 约束和部分索引经常漏)
alembic revision -m "add xx column"

# autogenerate(生成后必须人肉逐行 review,它会把你没预料到的
# 模型改动全部写进去)
alembic revision --autogenerate -m "add xx column"
```

## 三步加列纪律

线上加列一律三步走,禁止一步到位:

1. **加可空列**(或带 server_default):`op.add_column(...)`,对线上无锁风险,老代码不认识新列也不受影响。
2. **发版双写/回填**:应用写入新列,存量数据用 `scripts/backfill_tenant.py` 这类批量脚本分批刷,每批一个事务。
3. **收紧约束**:回填完成后另起一个迁移,把列改成 `NOT NULL` 或补 default。

为什么:直接 `ALTER TABLE ... SET NOT NULL` 在大表上是全表扫描,pg 12 以前还会锁写。吃过亏的票:#VT-1902。

## 大表索引必须 CONCURRENTLY

`op.create_index` 默认走普通 `CREATE INDEX`,会锁写。行数上千万的表(audit_logs、order_lines、stock_ledgers)一律:

```python
op.execute(
    "CREATE INDEX CONCURRENTLY ix_audit_logs_action_tenant "
    "ON audit_logs (action, tenant_id)"
)
```

注意两点:

- `CREATE INDEX CONCURRENTLY` 不能在事务里跑,迁移要配 `op.get_context().autocommit_block()` 或让迁移整体非事务(该迁移的 upgrade/downgrade 全用 `op.execute`)。
- CONCURRENTLY 失败会留下 INVALID 索引,重跑前先 `DROP INDEX` 干掉残骸,不然查询规划器可能踩上去变慢。

写 down 时对应 `DROP INDEX CONCURRENTLY`。

## 其它约定

- revision 是 12 位十六进制,单头单根,不允许多头(合并分支迁移必须先消掉)。
- 迁移一旦进过主干并被预发执行过,只允许追加修正迁移,不允许改历史文件。
- downgrade 必须可执行,评审时跑 `alembic downgrade -1 && alembic upgrade head` 验证。
- 涉及枚举/状态字符串的变更,先看 `vela/db/types.py` 头注释——存量数据存的是字符串,别把旧值改没。
