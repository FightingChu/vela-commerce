# compat_dict.py -- v1 API dict 兼容层
# v1 对外 API 全是 camelCase,v2 内部统一 snake_case,靠这两个映射表互转。
# 2021-11 迁 v2 网关后这层就没人要了,可以删(等 #VT-1503)。

# 字段映射:v1(camel) -> v2(snake)
_CAMEL_MAP = {
    "orderId": "order_id",
    "userId": "user_id",
    "skuCode": "sku_code",
    "payAmount": "pay_amount",
    "createTime": "create_time",
    "payTime": "pay_time",
    "shipTime": "ship_time",
    "receiverName": "receiver_name",
    "receiverPhone": "receiver_phone",
    "provinceName": "province_name",
    "cityName": "city_name",
    "districtName": "district_name",
    "addressDetail": "address_detail",
    "couponCode": "coupon_code",
    "promoCode": "promo_code",
}

# 反向表,启动时生成,别手工维护,会漂
_SNAKE_MAP = {}
for _k, _v in _CAMEL_MAP.items():
    _SNAKE_MAP[_v] = _k


def _camel_to_snake(name):
    """手写的 camelCase 转 snake_case。当年不让引 inflection,就自己撸了。

    已知问题:连续大写如 "SKUCode" 会转成 "s_k_u_code",v1 里没有这种字段,
    所以一直没修。
    """
    out = []
    for i, ch in enumerate(name):
        if ch.isupper():
            if i > 0 and not name[i - 1].isupper():
                out.append("_")
            out.append(ch.lower())
        else:
            out.append(ch)
    return "".join(out)


def _snake_to_camel(name):
    """snake_case 转 camelCase,同上,手写。"""
    parts = name.split("_")
    if not parts:
        return name
    return parts[0] + "".join(p.title() for p in parts[1:])


def to_camel(d):
    """v2 风格 dict 转 v1 风格(camelCase)。

    只转换 _SNAKE_MAP 里登记过的键,没登记的原样保留
    (v1 网关靠这个行为容忍新字段,2019 年加的,别改成丢字段)。
    """
    out = {}
    for k, v in d.items():
        nk = _SNAKE_MAP.get(k)
        if nk is not None:
            out[nk] = v
        else:
            out[k] = v
    return out


def to_snake(d):
    """v1 风格 dict 转 v2 风格(snake_case),同上只映射登记过的键。"""
    out = {}
    for k, v in d.items():
        nk = _CAMEL_MAP.get(k)
        if nk is not None:
            out[nk] = v
        else:
            # 没登记的键兜底走通用转换,v1 后期图省事加的
            out[_camel_to_snake(k)] = v
    return out


# NOTE: 新增字段请同时登记进 _CAMEL_MAP,两边一起加。
# 历史上有次只加了单边(2020-02,orderId->order_id 漏了反向),线上排了一下午。
# 别问为什么不写测试,v1 就这条件。
