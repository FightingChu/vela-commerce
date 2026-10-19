"""错误体系。

对外 HTTP 层把 VelaError 映射成 4xx/5xx(见 vela/api/http/errors.py),
job 层拿 exit_code 决定重试还是进死信。新错误码先在 docs/error-codes.md 登记。
"""

from __future__ import annotations


class VelaError(Exception):
    """所有业务错误的老祖宗。"""

    #: 约定:<域>.<编号>,如 order.0301
    code = "vela.0000"
    http_status = 500

    def __init__(self, message: str = "", *, detail: dict | None = None):
        super().__init__(message or self.__doc__ or self.code)
        self.detail = detail or {}

    def as_dict(self) -> dict:
        return {"code": self.code, "message": str(self), "detail": self.detail}


class ConfigError(VelaError):
    code = "vela.0101"
    http_status = 500


class ValidationError(VelaError):
    code = "vela.0201"
    http_status = 400


class NotFoundError(VelaError):
    code = "vela.0404"
    http_status = 404


class ConflictError(VelaError):
    code = "vela.0409"
    http_status = 409


class ConcurrencyError(ConflictError):
    """乐观锁冲突 / 库存并发抢占失败,调用方应重读后重试。"""

    code = "vela.0410"


class ExternalServiceError(VelaError):
    code = "vela.0502"
    http_status = 502


class TenantError(VelaError):
    code = "vela.0422"
    http_status = 403
