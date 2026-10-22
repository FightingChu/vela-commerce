"""应用工厂。

blueprint 手工罗列,没用自动扫描:注册顺序排查问题时肉眼可读,
加资源就加一行。/healthz 探活不连库会误报,所以 db 项是真连,
探不动标 degraded 但仍回 200,让 LB 先摘流量再报警。
"""

from __future__ import annotations

from flask import Flask, jsonify

from vela.api.http.errors import error_response
from vela.api.middleware import register_middleware
from vela.config.errors import VelaError
from vela.config.logging import get_logger

log = get_logger(__name__)


# 注册清单。import 放函数内会拖慢首请求,放模块顶就要求所有 blueprint
# 模块 import 时零副作用(不连库不建表),这个约定别破。
from vela.api.http.audit_logs import bp as audit_logs_bp  # noqa: E402
from vela.api.http.coupon_redemptions import bp as coupon_redemptions_bp  # noqa: E402
from vela.api.http.coupons import bp as coupons_bp  # noqa: E402
from vela.api.http.customer_addresses import bp as customer_addresses_bp  # noqa: E402
from vela.api.http.customers import bp as customers_bp  # noqa: E402
from vela.api.http.exports import bp as exports_bp  # noqa: E402
from vela.api.http.health_extra import bp as health_extra_bp  # noqa: E402
from vela.api.http.merchants import bp as merchants_bp  # noqa: E402
from vela.api.http.order_admin import bp as order_admin_bp  # noqa: E402
from vela.api.http.order_lines import bp as order_lines_bp  # noqa: E402
from vela.api.http.orders import bp as orders_bp  # noqa: E402
from vela.api.http.payment_callbacks import bp as payment_callbacks_bp  # noqa: E402
from vela.api.http.pricebook import bp as pricebook_bp  # noqa: E402
from vela.api.http.prices import bp as prices_bp  # noqa: E402
from vela.api.http.promotions import bp as promotions_bp  # noqa: E402
from vela.api.http.reconcile import bp as reconcile_bp  # noqa: E402
from vela.api.http.refunds import bp as refunds_bp  # noqa: E402
from vela.api.http.reservations import bp as reservations_bp  # noqa: E402
from vela.api.http.settlement_lines import bp as settlement_lines_bp  # noqa: E402
from vela.api.http.settlements import bp as settlements_bp  # noqa: E402
from vela.api.http.skus import bp as skus_bp  # noqa: E402
from vela.api.http.statements import bp as statements_bp  # noqa: E402
from vela.api.http.stock import bp as stock_bp  # noqa: E402
from vela.api.http.tax_rates import bp as tax_rates_bp  # noqa: E402
from vela.api.http.tenants import bp as tenants_bp  # noqa: E402
from vela.api.http.warehouses import bp as warehouses_bp  # noqa: E402

_BLUEPRINTS = (
    orders_bp,
    order_lines_bp,
    refunds_bp,
    order_admin_bp,
    skus_bp,
    stock_bp,
    reservations_bp,
    warehouses_bp,
    pricebook_bp,
    prices_bp,
    tax_rates_bp,
    coupons_bp,
    coupon_redemptions_bp,
    promotions_bp,
    customers_bp,
    customer_addresses_bp,
    settlements_bp,
    settlement_lines_bp,
    statements_bp,
    merchants_bp,
    audit_logs_bp,
    tenants_bp,
    exports_bp,
    payment_callbacks_bp,
    reconcile_bp,
    health_extra_bp,
)


def create_app() -> Flask:
    app = Flask("vela.api")
    app.config["JSON_SORT_KEYS"] = False

    register_middleware(app)
    register_error_handlers(app)

    for bp in _BLUEPRINTS:
        app.register_blueprint(bp)

    @app.get("/healthz")
    def healthz():
        db_ok = _check_db()
        bus_ok = _check_bus()
        return jsonify(
            {
                "status": "ok" if db_ok and bus_ok else "degraded",
                "db": db_ok,
                "bus": bus_ok,
            }
        )

    return app


def register_error_handlers(app: Flask) -> None:
    @app.errorhandler(VelaError)
    def _vela_error(exc):
        return error_response(exc)

    # pydantic 校验失败映射成 400。只取第一条,detail 不外吐(报文回显
    # 曾被拿来探测字段,#VT-2012 之后统一砍掉)
    from pydantic import ValidationError as PydanticValidationError

    @app.errorhandler(PydanticValidationError)
    def _bad_request(exc):
        errors = exc.errors()
        if errors:
            first = errors[0]
            loc = ".".join(str(p) for p in first.get("loc", ()))
            message = f"参数校验失败: {loc} {first.get('msg', '')}".strip()
        else:
            message = "参数校验失败"
        return jsonify({"code": "vela.0201", "message": message}), 400

    # 框架级 404/405 也回 JSON,客户端只认一种错误格式
    @app.errorhandler(404)
    def _not_found(_exc):
        return jsonify({"code": "vela.http.0404", "message": "路由不存在"}), 404

    @app.errorhandler(405)
    def _bad_method(_exc):
        return jsonify({"code": "vela.http.0405", "message": "方法不允许"}), 405

    @app.errorhandler(500)
    def _internal(exc):
        # 非 VelaError 的异常走这里,VelaError 有自己的 handler,不会进来
        log.error("api_internal_error", error=str(exc))
        return jsonify({"code": "vela.http.0500", "message": "内部错误"}), 500


def _check_db() -> bool:
    from sqlalchemy import text

    from vela.db.engine import primary_engine

    try:
        with primary_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:  # 探活不许抛,挂了就标 False
        return False


def _check_bus() -> bool:
    from vela.messaging.bus import get_bus

    try:
        get_bus()
        return True
    except Exception:
        return False
