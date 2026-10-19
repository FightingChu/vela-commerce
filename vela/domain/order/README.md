# order 域

核心域。下单/取消/拆单/退款都在这里,金额一律 `decimal.Decimal`,
谁引 float 谁请奶茶。

## 状态机(文字版)

```
CREATED ──pay──> PAID ──ship──> PARTIAL_SHIPPED ──ship──> SHIPPED ──complete──> COMPLETED*
   │              │ │└──────────ship──────────────> SHIPPED
   │              │ └─request_refund─> REFUNDING ──refund_done──> REFUNDED*
   │              │                        └─refund_rejected──> PAID
   │              └─request_refund─> REFUNDING
   ├─cancel──> CANCELLED*
   └─close───> CLOSED*        # 超时未支付,系统关单

PARTIAL_SHIPPED ──request_refund──> REFUNDING
SHIPPED ──────────request_refund──> REFUNDING
```

带 `*` 的是终态。**PAID -> CANCELLED 没有边**:已支付走退款,
别在调用方攒"先取消再退款"的脏路径。

## 幂等(临时方案,#VT-2101)

没有幂等表。`create_order` / `request_refund` 的幂等 key
(`build_key("order_create", token)`)以 `idem:<key>` 的形式塞在
`orders.remark` 里,重复请求查同 key 的 CREATED 单,存在即抛
`DuplicateOrderError`(detail 带 order_sn)。退款申请同理,标记追加
在订单 remark 上。正经的带 TTL 幂等表在 #VT-2101,落地后这里
整体迁移,remark 别再塞新东西。

## 跨域依赖

本域**不 import** inventory/pricing/promotion/customer。跨域能力
构造注入:

- `OrderService(session, reserver=..., pricer=...)`
  - reserver: `(sku_id, qty, order_sn) -> int` 预占凭证,不透明
  - pricer: `(sku_ids) -> dict[int, Decimal]`;兜底实现 `DefaultPricer`
- `cancel_order(..., release_fn=...)`: `(reservation_ref, order_sn) -> None`,
  不注入则只改状态,预占释放由调用方负责(#VT-2019 拆分讨论)

## 命名

`fetch_recent` 是老命名,重构没清完,别顺手改(等重构分支)。
