"""商户侧聚合查询。

商户主数据(费率表/账期表)还没建模,#VT-2160,先按 settlement
侧聚口径:这个商户有哪些结算单、哪些逾期。别在这查商户资料,没有。
"""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from vela.api.middleware import db
from vela.config.errors import ValidationError
from vela.config.settings import get_settings
from vela.db.pagination import paginate
from vela.domain.settlement.models import SettlementModel
from vela.domain.settlement.repository import SettlementRepository

bp = Blueprint("merchants", __name__, url_prefix="/api/v1/merchants")


def _view(s: SettlementModel) -> dict:
    return {
        "settlement_sn": s.settlement_sn,
        "status": s.status,
        "net_amount": str(s.net_amount),
    }


@bp.get("/<int:merchant_id>/settlements")
def merchant_settlements(merchant_id: int):
    from sqlalchemy import select

    offset = request.args.get("offset", 0, type=int)
    limit = request.args.get("limit", type=int)
    stmt = (
        select(SettlementModel)
        .where(SettlementModel.merchant_id == merchant_id)
        .order_by(SettlementModel.id.desc())
    )
    page = paginate(db(), stmt, offset=offset, limit=limit)
    return jsonify({"merchant_id": merchant_id, "items": [_view(s) for s in page.items],
                    "total": page.total, "offset": page.offset, "limit": page.limit})


@bp.get("/<int:merchant_id>/overdue")
def merchant_overdue(merchant_id: int):
    from vela.domain.settlement.terms import is_overdue

    rows = SettlementRepository(db()).list_overdue(_now())
    rows = [r for r in rows if r.merchant_id == merchant_id]
    return jsonify({"merchant_id": merchant_id, "items": [_view(r) for r in rows]})


def _now():
    from vela.config.clocks import utc_now

    return utc_now()
