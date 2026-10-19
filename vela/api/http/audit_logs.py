"""审计日志查询。只读,写入只发生在 AuditService,别开 POST。"""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from vela.api.middleware import db
from vela.config.errors import NotFoundError
from vela.db.pagination import paginate
from vela.auditing.models import AuditLogModel

bp = Blueprint("audit_logs", __name__, url_prefix="/api/v1/audit-logs")


def _view(r: AuditLogModel) -> dict:
    return {
        "id": r.id,
        "actor": r.actor,
        "action": r.action,
        "target_type": r.target_type,
        "target_id": r.target_id,
        "detail": r.detail,
        "trace": r.trace,
        "created_at": r.created_at.isoformat() if getattr(r, "created_at", None) else None,
    }


@bp.get("")
def list_logs():
    from sqlalchemy import select

    offset = request.args.get("offset", 0, type=int)
    limit = request.args.get("limit", type=int)
    stmt = select(AuditLogModel).order_by(AuditLogModel.id.desc())
    for col in ("actor", "action", "trace"):
        val = request.args.get(col)
        if val:
            stmt = stmt.where(getattr(AuditLogModel, col) == val)
    page = paginate(db(), stmt, offset=offset, limit=limit)
    return jsonify({"items": [_view(r) for r in page.items],
                    "total": page.total, "offset": page.offset, "limit": page.limit})


@bp.get("/<int:log_id>")
def get_log(log_id: int):
    from vela.db.repository import Repository

    try:
        row = Repository(AuditLogModel)(db()).get(log_id)
    except NotFoundError:
        raise NotFoundError(f"审计记录 {log_id} 不存在", detail={"log_id": log_id}) from None
    return jsonify(_view(row))
