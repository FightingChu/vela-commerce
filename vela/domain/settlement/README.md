# settlement 域

结算单(对账单)域:把一段时间内的成交/退款行汇总成结算单,
确认账期,推送渠道清分,最后结清并和渠道侧对账。

## 状态流转

draft -> confirmed -> pushed -> settled,任何非终态可落 failed。
FAILED 是终态,没有回退边(2025-08 对账事故复盘定的,#VT-2077),
修数后重开新单。

## 账期规则

- `due_date = confirmed_at + terms_days`,从 confirm 时刻起算,
  不是 period_end(财务 2025Q3 定的口径)。
- terms_days 建单时从商户费率/账期表快照进单子,后期改表不影响已建单。
- 商户表缺配置时用平台默认 30 天,费率用 `DEFAULT_FEE_RATE`。
- 逾期 = 未 SETTLED 且 due_date 已过,见 `terms.is_overdue`。

## 费用口径

逐行 `round_half_up(amount * fee_rate)` 后再合计,不先合金额再算费,
和渠道侧对齐(#VT-2003)。REFUND 行费用为负(按费率退)。

## 幂等键范围

`create_settlement` 的幂等口径是“merchant_id + 规范化后的 token”。
落库仍使用兼容格式 `settlement_push:<token>`，查重同时限定商户和
完整 key，避免跨商户误拦，也避免前后缀或 SQL 通配符造成误命中。
`None`、空白、`-1`、`null`、`undefined` 继续表示旧调用方不启用幂等。

这修复了 #VT-2217 的跨商户误拦和相似 token 误命中问题。
