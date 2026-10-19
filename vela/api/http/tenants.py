"""租户注册表。bootstrap 级接口,只有运维平台和测试会调。"""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from vela.api.middleware import db
from vela.api.schemas import TenantIn
from vela.tenancy.models import Plan
from vela.tenancy.registry import TenantRegistry

bp = Blueprint("tenants", __name__, url_prefix="/api/v1/tenants")


def _view(t) -> dict:
    return {
        "id": t.id,
        "tenant_id": t.tenant_id,
        "name": t.name,
        "plan": t.plan,
        "enabled": t.enabled,
        "shard_hint": t.shard_hint,
    }


@bp.get("")
def list_tenants():
    rows = TenantRegistry(db()).list_active()
    return jsonify({"items": [_view(t) for t in rows]})


@bp.post("")
def register_tenant():
    payload = TenantIn.model_validate(request.get_json(silent=True) or {})
    row = TenantRegistry(db()).register(
        payload.tenant_id, payload.name, plan=Plan(payload.plan).value
    )
    if payload.shard_hint:
        row.shard_hint = payload.shard_hint
    db().commit()
    return jsonify(_view(row)), 201


@bp.get("/<tenant_id>")
def get_tenant(tenant_id: str):
    row = TenantRegistry(db()).find_by_tenant(tenant_id)
    if row is None:
        from vela.config.errors import NotFoundError

        raise NotFoundError(f"租户未注册: {tenant_id}", detail={"tenant_id": tenant_id})
    return jsonify(_view(row))
