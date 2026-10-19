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

## 已知问题 #VT-2217:幂等键没带 merchant scope

`create_settlement` 的幂等键完整形式是 `settlement_push:<token>`,
idem_key 列里存的是完整 key;但查重逻辑是历史遗留,只按 token 后缀
模糊匹配(`idem_key LIKE '%<token>'`),既没限定 merchant_id 也没
校验 scope 前缀。后果:

- 跨商户同 token 会误拦(A 商户先推,B 商户同 token 被拒);
- LIKE 匹配到别的 scope 同 token 的键时漏拦,重推会重复入账
  (2025-07 线上真出过一笔重复结算,财务手工冲正)。

修复排期中。在那之前,**新代码构造幂等键必须带 scope 前缀并用
`build_key`,禁止手拼字符串**;查重逻辑别"顺手修"——有特征测试
锁着现状,改动要连测试和 #VT-2217 一起过。
