"""结算明细行。SettlementLineModel 没有专门 repo,够简单就不加了。"""

from __future__ import annotations

from flask import Blueprint, jsonify

from vela.api.middleware import db
from vela.domain.settlement.models import SettlementLineModel
from vela.domain.settlement.repository import SettlementRepository

bp = Blueprint("settlement_lines", __name__, url_prefix="/api/v1/settlements")


@bp.get("/<settlement_sn>/lines")
def list_lines(settlement_sn: str):
    from sqlalchemy import select

    settlement = SettlementRepository(db()).get_by_sn(settlement_sn)
    rows = db().execute(
        select(SettlementLineModel)
        .where(SettlementLineModel.settlement_id == settlement.id)
        .order_by(SettlementLineModel.id)
    ).scalars().all()
    items = [
        {
            "id": ln.id,
            "order_sn": ln.order_sn,
            "kind": getattr(ln.kind, "value", str(ln.kind)),
            "amount": str(ln.amount),
            "fee": str(ln.fee),
        }
        for ln in rows
    ]
    return jsonify({"settlement_sn": settlement_sn, "items": items})
