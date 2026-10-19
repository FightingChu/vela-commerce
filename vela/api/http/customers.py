"""客户。注册/等级流转走 customer/service.py,查询直接 repo。"""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from vela.api.middleware import db
from vela.api.schemas import CustomerCreate, TierChange
from vela.db.pagination import paginate
from vela.domain.customer.models import CustomerModel
from vela.domain.customer.repository import CustomerRepository
from vela.domain.customer.service import register_customer, update_tier

bp = Blueprint("customers", __name__, url_prefix="/api/v1/customers")


def _view(c: CustomerModel) -> dict:
    # phone 本身就是脱敏后的,直接出
    return {
        "id": c.id,
        "external_id": c.external_id,
        "nickname": c.nickname,
        "phone": c.phone,
        "tier": c.tier,
        "registered_at": c.registered_at.isoformat() if c.registered_at else None,
    }


@bp.post("")
def create_customer():
    payload = CustomerCreate.model_validate(request.get_json(silent=True) or {})
    customer = register_customer(
        payload.external_id, payload.nickname,
        phone=payload.phone, tier=payload.tier, session=db(),
    )
    db().commit()
    return jsonify(_view(customer)), 201


@bp.get("")
def list_customers():
    from sqlalchemy import select

    offset = request.args.get("offset", 0, type=int)
    limit = request.args.get("limit", type=int)
    page = paginate(db(), select(CustomerModel).order_by(CustomerModel.id),
                    offset=offset, limit=limit)
    return jsonify({"items": [_view(c) for c in page.items],
                    "total": page.total, "offset": page.offset, "limit": page.limit})


@bp.get("/<int:customer_id>")
def get_customer(customer_id: int):
    return jsonify(_view(CustomerRepository(db()).get(customer_id)))


@bp.post("/<int:customer_id>/tier")
def change_tier(customer_id: int):
    payload = TierChange.model_validate(request.get_json(silent=True) or {})
    if payload.customer_id != customer_id:
        from vela.config.errors import ValidationError

        raise ValidationError("路径与 body 的 customer_id 不一致")
    customer = update_tier(customer_id, payload.tier, session=db())
    db().commit()
    return jsonify(_view(customer))
