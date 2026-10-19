"""促销域错误码。新码先去 docs/error-codes.md 登记(规约见 config/errors.py)。"""

from __future__ import annotations

from vela.config.errors import ConflictError, ValidationError


class CouponUnavailableError(ValidationError):
    """券不可用:不存在 / 停用 / 不在有效期 / 未达门槛。

    归 400 而不是 404——运营侧反馈"下单时告诉我券不存在"对用户不友好,
    前端统一展示 detail.reason 即可。
    """

    code = "promotion.0201"


class CouponExhaustedError(ConflictError):
    """总量发光了。抢券和核销都会走到这。"""

    code = "promotion.0409"


class QuotaExceededError(ConflictError):
    """单人超领(per_customer_limit)。"""

    code = "promotion.0410"
