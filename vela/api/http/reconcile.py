"""库存对账。快照来自 inventory/reconcile.py,凌晨 job 也用同一套。"""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from vela.api.middleware import db
from vela.api.schemas import ReconcileRunIn
from vela.domain.inventory.reconcile import diff, emit_reconcile_event, take_snapshot

bp = Blueprint("reconcile", __name__, url_prefix="/api/v1/reconcile")


def _key_str(key: tuple) -> str:
    return f"{key[0]}:{key[1]}"


@bp.get("/snapshot")
def snapshot():
    snap = take_snapshot(db())
    return jsonify({"items": {_key_str(k): v for k, v in sorted(snap.items())}})


@bp.post("/run")
def run():
    payload = ReconcileRunIn.model_validate(request.get_json(silent=True) or {})
    actual = take_snapshot(db())
    if payload.expected is None:
        # 只出快照,不比对,给盘点导入前先看现状用
        return jsonify({"dry_run": payload.dry_run, "diff": [], "snapshot": {
            _key_str(k): v for k, v in sorted(actual.items())
        }})
    expected = {}
    for raw_key, qty in payload.expected.items():
        try:
            sku_part, wh_part = raw_key.split(":", 1)
            expected[(int(sku_part), wh_part)] = qty
        except ValueError:
            from vela.config.errors import ValidationError

            raise ValidationError(f"expected 键格式应为 sku_id:warehouse: {raw_key!r}") from None
    rows = diff(expected, actual)
    event = None
    if rows and not payload.dry_run:
        # 非 dry run 才发对账事件,告警那头订阅 EVENT_RECONCILE_DONE
        event = emit_reconcile_event(rows)
    return jsonify({"dry_run": payload.dry_run, "diff_count": len(rows), "diff": rows,
                    "event": event})
