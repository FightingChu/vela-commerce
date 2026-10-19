"""order 域错误。

新错误码先去 docs/error-codes.md 登记(虽然经常忘,见 #VT-1960)。
"""

from __future__ import annotations

from vela.config.errors import ConflictError, NotFoundError


class OrderStateError(ConflictError):
    """状态机不允许的流转。detail 带 current / allowed。"""

    code = "order.0409"


class OrderNotFoundError(NotFoundError):
    """按单号查不到,或已被软删。"""

    code = "order.0404"


class DuplicateOrderError(ConflictError):
    """幂等 token 命中已存在的单。detail 里带 order_sn,网关拿它做回查。"""

    code = "order.0411"
