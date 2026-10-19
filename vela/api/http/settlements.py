"""结算单。创建/流转都过 SettlementService,幂等 token 原样透传。"""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from vela.api.middleware import db
from vela.api.schemas import SettlementCreate
from vela.domain.settlement.models import SettlementModel
from vela.domain.settlement.repository import SettlementRepository
from vela.domain.settlement.service import SettlementService

bp = Blueprint("settlements", __name__, url_prefix="/api/v1/settlements")


def _view(s: SettlementModel) -> dict:
    return {
        "settlement_sn": s.settlement_sn,
        "merchant_id": s.merchant_id,
        "status": s.status,
        "gross_amount": str(s.gross_amount),
        "fee_amount": str(s.fee_amount),
        "net_amount": str(s.net_amount),
        "terms_days": s.terms_days,
    }


@bp.post("")
def create_settlement():
    payload = SettlementCreate.model_validate(request.get_json(silent=True) or {})
    svc = SettlementService(db())
    model = svc.create_settlement(
        payload.merchant_id,
        payload.orders,
        token=payload.token,
        terms_days=payload.terms_days,
    )
    db().commit()
    return jsonify(_view(model)), 201


@bp.get("")
def list_settlements():
    from sqlalchemy import select

    from vela.db.pagination import paginate

    offset = request.args.get("offset", 0, type=int)
    limit = request.args.get("limit", type=int)
    stmt = select(SettlementModel).order_by(SettlementModel.id.desc())
    merchant_id = request.args.get("merchant_id", type=int)
    if merchant_id:
        stmt = stmt.where(SettlementModel.merchant_id == merchant_id)
    page = paginate(db(), stmt, offset=offset, limit=limit)
    return jsonify({"items": [_view(s) for s in page.items],
                    "total": page.total, "offset": page.offset, "limit": page.limit})


@bp.get("/<settlement_sn>")
def get_settlement(settlement_sn: str):
    return jsonify(_view(SettlementRepository(db()).get_by_sn(settlement_sn)))


@bp.post("/<settlement_sn>/confirm")
def confirm(settlement_sn: str):
    model = SettlementService(db()).confirm(settlement_sn)
    db().commit()
    return jsonify(_view(model))


@bp.post("/<settlement_sn>/settle")
def settle(settlement_sn: str):
    model = SettlementService(db()).mark_settled(settlement_sn)
    db().commit()
    return jsonify(_view(model))
