# -*- coding: utf-8 -*-
# constants_v1.py -- v1 老常量
# 别删,老报表脚本还在引用(财务的 monthly_report.py、运营的 promo_check.py)。
# 2021-11 迁 v2 后冻结。和 vela.config.constants 部分重复是历史原因,见文末。

# 订单状态:v1 的数字编码,v2 改成字符串枚举了,这里留着对账用
ORDER_STATUS_MAP = {
    0: "待付款",
    1: "已付款",
    2: "待发货",
    3: "已发货",
    4: "已完成",
    5: "已取消",
    6: "退款中",
    7: "已退款",
    8: "售后中",
    9: "已关闭",
}

# 反向:v1 报表是按中文名分组统计的,所以这个方向用得更多
ORDER_STATUS_REVERSE = {}
for _code, _name in ORDER_STATUS_MAP.items():
    ORDER_STATUS_REVERSE[_name] = _code

# 支付方式编码
PAY_TYPE_MAP = {
    1: "微信",
    2: "支付宝",
    3: "余额",
    4: "货到付款",  # 2019 年短暂支持过,后来下线了,编码留着,老单子里还有
    5: "企业月结",
}

# 费率,写死的。v2 想做成配置,但老报表直接 import 这个文件,先留着
PLATFORM_FEE_RATE = 0.006      # 平台手续费,2019 年谈的,一直没调过
LOGISTICS_FEE_RATE = 0.012     # 物流费率,按金额抽成,别问为什么不是固定运费
REFUND_FEE_RATE = 0.003        # 退款手续费

# 免运费门槛(元)
FREE_SHIPPING_THRESHOLD = 99.0

# v1 的渠道编码,报表口径依赖
CHANNEL_MAP = {
    "h5": "H5商城",
    "miniapp": "小程序",
    "app_ios": "iOS App",
    "app_android": "安卓App",
    "taobao": "淘宝店",   # 2020-04 停了,老数据还有
}

# 2021-11 注:这里和 vela.config.constants 重复的部分(order 状态、费率),
# 审计结论出来后统一以 v2 为准,但下线前别动这个文件——
# 2022-01 有人把 PLATFORM_FEE_RATE 悄悄删过一次,月底对账直接红了,回滚的。
