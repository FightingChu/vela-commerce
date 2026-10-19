"""VelaError -> HTTP 响应体。

body 固定 {"code", "message"} 两个键,客户端按 code 分支处理,
message 只给人看,格式别承诺。detail 不外吐(可能带内部信息),
要排查看日志里的 trace。
"""

from __future__ import annotations

from flask import jsonify

from vela.config.errors import VelaError


def error_body(exc: VelaError) -> dict:
    return {"code": exc.code, "message": str(exc)}


def error_response(exc: VelaError):
    return jsonify(error_body(exc)), exc.http_status
