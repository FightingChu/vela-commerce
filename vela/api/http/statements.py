"""对账单试算。build_statement 是纯函数,适合直接暴露给商户后台预览。"""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from vela.config.errors import ValidationError
from vela.domain.settlement.statement import build_statement
from vela.domain.shared import to_decimal

bp = Blueprint("statements", __name__, url_prefix="/api/v1/statements")


@bp.post("/preview")
def preview():
    body = request.get_json(silent=True) or {}
    rows = body.get("orders")
    fee_rate = body.get("fee_rate")
    if rows is None or fee_rate is None:
        raise ValidationError("orders/fee_rate 必填")
    # 纯计算不落库。落正式结算单走 POST /api/v1/settlements
    result = build_statement(rows, fee_rate=to_decimal(fee_rate))
    out = dict(result)
    out["lines"] = [
        {**line, "amount": str(line["amount"]), "fee": str(line["fee"])}
        for line in result["lines"]
    ]
    out["gross"] = str(result["gross"])
    out["refund_total"] = str(result["refund_total"])
    out["fee"] = str(result["fee"])
    out["net"] = str(result["net"])
    return jsonify(out)
