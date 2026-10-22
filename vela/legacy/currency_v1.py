# currency_v1.py -- 老汇率表,硬编码
# 2023-01 冻结,已停更。当时决定:跨境业务收归 v2,这里只服务老报表的
# 历史区间换算(2022 年及以前的订单金额折算),所以数值就停在 2023-01-01。
# 别拿去做实时换算!!!

# 对人民币汇率,USD/CNY 起头,后面是当年陆续接的币种
_RATES = {
    "USD": 7.2,
    "EUR": 7.65,
    "GBP": 8.85,
    "JPY": 0.052,      # 日元是按 1 单位算的,当年有同事按 100 算过一次,排了半天
    "HKD": 0.92,
    "CNY": 1.0,
}

# 冻结日期,报表脚本来读这个决定要不要警告
RATES_FROZEN_AT = "2023-01-01"


def convert(amount, code):
    """把外币金额折成人民币。

    code 不认识就原样返回,并打日志(v1 行为:宁可不错报,别挂报表)。
    """
    rate = _RATES.get(code)
    if rate is None:
        # 2022-08 有报表传过 "usd" 小写挂掉,后来加了这层
        rate = _RATES.get(str(code).upper() if code else "")
    if rate is None:
        print("[currency_v1] unknown currency: %r, return as-is" % (code,))
        return amount
    return amount * rate


def known_currencies():
    """返回支持的币种列表,老报表的表头是按这个生成的。"""
    return list(_RATES.keys())


# ---- 历史 ----
# 2019-06 建,当时是一个 cron 每天抓中行牌价更新这个文件再提交 git
# (对,自动提交,git log 里一排 "bot: update rates"),2021 年 v2 接了
# 实时汇率之后 cron 停了,2023-01 决定彻底冻结。
# TODO: 老报表迁完 v2 的历史区间接口后,这个文件可以删,见 #VT-1503
