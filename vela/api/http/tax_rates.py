"""税率查询。静态表口径以 #VT-2076 登记的计税规则为准。

rate 用 str 传输,和金额口径一致;TaxRate 的 0~0.5 校验在构造时兜底。
"""

from __future__ import annotations

from flask import Blueprint, jsonify

from vela.config.errors import NotFoundError
from vela.domain.pricing.tax import TaxRate

bp = Blueprint("tax_rates", __name__, url_prefix="/api/v1/tax-rates")

# region -> rate。加税率改这里,别处不许散落写死
_TAX_TABLE = {
    "CN": "0.13",
    "JP": "0.10",
    "SG": "0.09",
    "DE": "0.19",
}


def _rate_of(region: str) -> TaxRate:
    raw = _TAX_TABLE.get(region.upper())
    if raw is None:
        raise NotFoundError(f"未知税区: {region}", detail={"region": region})
    return TaxRate(raw)


@bp.get("")
def list_tax_rates():
    return jsonify({"items": [{"region": r, "rate": raw} for r, raw in sorted(_TAX_TABLE.items())]})


@bp.get("/<region>")
def get_tax_rate(region: str):
    rate = _rate_of(region)
    return jsonify({"region": region.upper(), "rate": str(rate.value)})
