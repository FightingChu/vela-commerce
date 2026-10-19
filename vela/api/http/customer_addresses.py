"""收货地址。挂在客户路径下,默认地址唯一性由 service 层维护。"""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from vela.api.middleware import db
from vela.api.schemas import AddressIn
from vela.domain.customer.models import AddressModel
from vela.domain.customer.repository import AddressRepository
from vela.domain.customer.service import set_default_address

bp = Blueprint(
    "customer_addresses", __name__,
    url_prefix="/api/v1/customers/<int:customer_id>/addresses",
)


def _view(a: AddressModel) -> dict:
    return {
        "id": a.id,
        "customer_id": a.customer_id,
        "receiver": a.receiver,
        "phone": a.phone,
        "province": a.province,
        "city": a.city,
        "district": a.district,
        "detail": a.detail,
        "is_default": a.is_default,
    }


@bp.get("")
def list_addresses(customer_id: int):
    rows = AddressRepository(db()).list_addresses(customer_id)
    return jsonify({"items": [_view(a) for a in rows]})


@bp.post("")
def create_address(customer_id: int):
    payload = AddressIn.model_validate(request.get_json(silent=True) or {})
    addr = AddressModel(
        customer_id=customer_id,
        receiver=payload.receiver,
        phone=payload.phone,
        province=payload.province,
        city=payload.city,
        district=payload.district,
        detail=payload.detail,
        is_default=payload.is_default,
    )
    repo = AddressRepository(db())
    repo.add(addr)
    db().flush()
    if payload.is_default:
        # 走 service 把同客户其余默认清掉,别手工 update
        set_default_address(customer_id, addr.id, session=db())
    db().commit()
    return jsonify(_view(addr)), 201


@bp.post("/<int:address_id>/default")
def make_default(customer_id: int, address_id: int):
    addr = set_default_address(customer_id, address_id, session=db())
    db().commit()
    return jsonify(_view(addr))
