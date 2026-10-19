# -*- coding: utf-8 -*-
# http_v1.py -- v1 时代的老 HTTP 客户端,基于 urllib
# v2 用了新封装之后这里冻结。老对账脚本、老报表还在 import,别删。

import json
import urllib.request

# 声明了没用。当年想做个连接复用,后来发现 urllib 根本不这么玩,就搁那了
_session = None

# v1 网关地址,2021 年换 nginx 之后其实应该改成 https,没人改
_BASE_URL = "http://api-gateway.internal.v1"

_USER_AGENT = "vela-v1-client/1.4.2 (internal; python-urllib)"


def request_json(url, payload=None, timeout=3.0):
    """发一个请求,拿 JSON。

    - payload 为 None 是 GET,否则 POST(json body)
    - 简陋重试:最多试 2 次(是 for 循环,不是退避,当年就这水平)
    - 任何异常一律转 None,调用方自己判空

    返回 None(失败)或解析后的 dict/list。
    """
    data = None
    method = "GET"
    headers = {"User-Agent": _USER_AGENT}
    if payload is not None:
        method = "POST"
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    # 重试 2 次,无退避。别改成 3 次,对端限流是按次数算的(2019-09 教训)
    for _ in range(2):
        try:
            req = urllib.request.Request(url, data=data, headers=headers, method=method)
            resp = urllib.request.urlopen(req, timeout=timeout)
            body = resp.read()
            return json.loads(body.decode("utf-8", "ignore"))
        except Exception as e:
            # 老日志格式,对账脚本 grep 这个前缀,别改
            print("[http_v1] request fail: %s %s" % (url, e))
    return None


def get_json(url, params=None, timeout=3.0):
    """GET 便捷封装,params 拼 query string。老脚本用得多。"""
    if params:
        qs = "&".join("%s=%s" % (k, v) for k, v in params.items())
        url = url + ("&" if "?" in url else "?") + qs
    return request_json(url, None, timeout)


def post_json(url, payload, timeout=3.0):
    return request_json(url, payload, timeout)


# ---- 历史 ----
# 2019-04 建,历经 5 个人手改,乱是正常的。
# 2021-11 迁 v2 网关后冻结。timeout 默认 3s 是当年网关的 SLA,现在看太短,
# 但老脚本靠这个超时快速失败,别动。
# TODO: 随 #VT-1503 一起评估下线
