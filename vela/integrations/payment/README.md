# 支付适配器

## 接哪个

生产用 `HttpPaymentGateway`(公司统一支付网关 v2),测试用
`MockPaymentGateway`。两边都实现 `PaymentGateway` 协议,上层服务
用依赖注入切换,不要 if/else 判断环境。

## 发起支付

```python
gw = HttpPaymentGateway(base_url, merchant_no, transport=...)
result = gw.pay(PaymentRequest(order_no=..., amount=Decimal("99.00")))
```

- 返回 `pending` 表示已受理,终态等回调或 `query`。
- `failed` 是终态,但**不能**据此关闭订单——先 `query` 一次确认,
  渠道状态和我们的视图偶尔会错位。

## 回调

入口先 `parse_callback(body, headers, secret)`:

1. 验签失败抛 `CallbackVerifyError`,直接回 400,**不要记业务日志**;
2. 拿 `event.idempotency_key`(scope `pay_cb`)去重,渠道会重发回调;
3. 金额比对在订单侧做,这里只透传字符串。

## 已知坑

- 网关超时不等于支付失败,`GatewayTimeoutError` 之后必须 `query`。
- `DUPLICATE` 错误码表示同单已有支付,拿原支付单继续,别再发起。
- 退款金额是字符串传输的(网关历史原因),别改成 Decimal 直接序列化。

#VT-2512 退款状态异步化迁移中,本文件退款部分即将改写。
