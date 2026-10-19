"""深度探活。/healthz 给 LB,/api/v1/health/detail 给值守大盘。

细节里带 db_url 会泄连接串,只出布尔和延迟毫秒。
"""

from __future__ import annotations

import time

from flask import Blueprint, jsonify

bp = Blueprint("health_extra", __name__, url_prefix="/api/v1/health")


@bp.get("/detail")
def detail():
    db_ms = None
    db_ok = False
    start = time.monotonic()
    try:
        from sqlalchemy import text

        from vela.db.engine import primary_engine

        with primary_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False
    finally:
        db_ms = round((time.monotonic() - start) * 1000, 1)

    from vela.config.settings import get_settings

    s = get_settings()
    return jsonify(
        {
            "env": s.env,
            "db": db_ok,
            "db_latency_ms": db_ms,
            "default_page_size": s.default_page_size,
            "max_page_size": s.max_page_size,
        }
    )
