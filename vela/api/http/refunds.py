"""退款。流转入口都在 order/returns.py,handler 只做参数翻译。"""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from vela.api.middleware import db
from vela.api.schemas import RefundRequest
from vela.config.constants import REFUND_SN_PREFIX
from vela.domain.order.returns import (
    approve_refund,
    mark_refund_done,
    request_refund,
)

bp = Blueprint("refunds", __name__, url_prefix="/api/v1/refunds")


def _view(r) -> dict:
    return {
        "refund_sn": r.refund_sn,
        "order_sn": r.order_sn,
        "amount": str(r.amount),
        "status": r.status,
        "reason": r.reason,
        "applied_at": r.applied_at.isoformat() if r.applied_at else None,
        "done_at": r.done_at.isoformat() if r.done_at else None,
    }


@bp.post("")
def create_refund():
    payload = RefundRequest.model_validate(request.get_json(silent=True) or {})
    refund = request_refund(
        db(), payload.order_sn, payload.amount, payload.reason, token=payload.token
    )
    db().commit()
    return jsonify(_view(refund)), 201


@bp.get("/<refund_sn>")
def get_refund(refund_sn: str):
    from vela.domain.order.returns import _load_refund

    return jsonify(_view(_load_refund(db(), refund_sn)))


@bp.post("/<refund_sn>/approve")
def approve(refund_sn: str):
    refund = approve_refund(db(), refund_sn)
    db().commit()
    return jsonify(_view(refund))


@bp.post("/<refund_sn>/complete")
def complete(refund_sn: str):
    # done 走完才 commit,失败 rollback 由 session_scope 语义兜底
    refund = mark_refund_done(db(), refund_sn)
    db().commit()
    return jsonify(_view(refund))
