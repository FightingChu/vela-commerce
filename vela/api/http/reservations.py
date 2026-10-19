"""预占。reserve/consume 走 reservation_service,release 直接 repo。"""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from vela.api.middleware import db
from vela.api.schemas import ReservationIn
from vela.domain.inventory.reservation_repo import ReservationRepository
from vela.domain.inventory.reservation_service import consume_reservation, reserve

bp = Blueprint("reservations", __name__, url_prefix="/api/v1/reservations")


def _view(r) -> dict:
    return {
        "id": r.id,
        "sku_id": r.sku_id,
        "warehouse": r.warehouse,
        "qty": r.qty,
        "released_qty": r.released_qty,
        "order_sn": r.order_sn,
        "status": getattr(r.status, "value", str(r.status)),
        "expires_at": r.expires_at.isoformat() if r.expires_at else None,
    }


@bp.post("")
def create_reservation():
    payload = ReservationIn.model_validate(request.get_json(silent=True) or {})
    rid = reserve(
        payload.sku_id,
        payload.qty,
        order_sn=payload.order_sn,
        warehouse=payload.warehouse,
        ttl_seconds=payload.ttl_seconds,
        session=db(),
    )
    db().commit()
    return jsonify({"reservation_id": rid}), 201


@bp.post("/<int:reservation_id>/consume")
def consume(reservation_id: int):
    body = request.get_json(silent=True) or {}
    consume_reservation(reservation_id, body.get("order_sn"), session=db())
    db().commit()
    return jsonify({"reservation_id": reservation_id, "status": "consumed"})


@bp.post("/<int:reservation_id>/release")
def release(reservation_id: int):
    body = request.get_json(silent=True) or {}
    rsv = ReservationRepository(db()).release(reservation_id, body.get("qty"))
    db().commit()
    return jsonify(_view(rsv))
